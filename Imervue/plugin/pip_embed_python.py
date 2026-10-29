"""
Portable Python for the dependency installer: download, verify and bootstrap pip.

When no interpreter with pip is found on Windows, :class:`_DownloadPythonWorker`
fetches CPython's embeddable zip and a pinned pip wheel, compares both against
pinned SHA-256 digests, extracts the zip (refusing zip-slip entries), enables
``import site`` and installs pip from the wheel. Every download goes through
the ``_https_urlopen`` guard in :mod:`Imervue.plugin.pip_installer`, which
re-exports this module's names.
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
import subprocess
import zipfile
from pathlib import Path
from urllib.request import Request

from PySide6.QtCore import QThread, Signal

from Imervue.plugin.python_finder import (
    _PYTHON_EXE_NAME,
    _embedded_python_dir,
    _subprocess_kwargs,
    _verify_python,
)
from Imervue.plugin.subprocess_util import terminate_process

logger = logging.getLogger("Imervue.plugin.pip_installer")


# ===========================
# 內嵌 Python 自動下載
# ===========================

# The last 3.12 release that ships an embeddable zip (later 3.12 releases are
# source-only). Keep the minor version equal to the frozen build's (release.yml):
# packages installed here are imported by the frozen app, so their cp312
# binaries must match its interpreter.
_EMBED_PYTHON_VERSION = "3.12.10"
_EMBED_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{_EMBED_PYTHON_VERSION}/"
    f"python-{_EMBED_PYTHON_VERSION}-embed-amd64.zip"
)
# SHA-256 of that zip: python.org publishes its MD5 (fe8ef205f2e9c3ba44d0cf9954e1abd3)
# and size (11,133,606 bytes), and a download matching both hashed to this.
_EMBED_PYTHON_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
# pip is installed from a pinned wheel whose SHA-256 is PyPI's published digest,
# not from get-pip.py: that script lives at a URL whose content changes with
# every pip release, so it could not be verified before being run.
_PIP_WHEEL_VERSION = "26.2.1"
_PIP_WHEEL_NAME = f"pip-{_PIP_WHEEL_VERSION}-py3-none-any.whl"
_PIP_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/f3/6e/"
    f"1736e5b4ae2b778ef2f81c47d797de9f891d4d8acb047a24ca37a60294dd/{_PIP_WHEEL_NAME}"
)
_PIP_WHEEL_SHA256 = "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e"
# Runs pip straight from its wheel, as ``python -m pip`` would: pip refuses to
# replace itself when started through any other entry point on Windows, and the
# embeddable Python ignores PYTHONPATH because of its ._pth file.
_PIP_FROM_WHEEL = (
    "import runpy, sys; wheel = sys.argv[1]; sys.path.insert(0, wheel); "
    "sys.argv = ['pip', 'install', '--no-index', '--no-warn-script-location', wheel]; "
    "runpy.run_module('pip', run_name='__main__', alter_sys=True)"
)
_USER_AGENT = "Imervue/1.0"
_UA_HEADERS = {"User-Agent": _USER_AGENT}
_PROCESS_TIMEOUT_MSG = "Process timed out"
_PTH_NAME_RE = re.compile(r"python[0-9._]*\._pth")


def _matches_sha256(data: bytes, expected: str) -> bool:
    """True if *data* hashes to the pinned hex SHA-256 *expected*."""
    return hashlib.sha256(data).hexdigest() == expected


class _DownloadPythonWorker(QThread):
    """背景下載並安裝 Python embeddable package"""
    log = Signal(str)
    result_ready = Signal(bool, str)  # success, python_exe_path or error

    def run(self):
        try:
            dest_dir = _embedded_python_dir()
            dest_dir.mkdir(parents=True, exist_ok=True)

            data = self._download_embed_zip()
            if data is None:
                return
            if not self._extract_safely(data, dest_dir):
                return

            python_exe = dest_dir / _PYTHON_EXE_NAME
            if not python_exe.is_file():
                self.result_ready.emit(False, f"{_PYTHON_EXE_NAME} not found after extraction")
                return

            self._patch_pth_files(dest_dir)

            if not self._bootstrap_pip(dest_dir, python_exe):
                return

            self.log.emit("Verifying pip ...")
            if not _verify_python(str(python_exe)):
                self.result_ready.emit(False, "pip verification failed after bootstrap")
                return

            self.log.emit("Python embeddable installed successfully!")
            self.result_ready.emit(True, str(python_exe))

        except Exception as exc:
            logger.exception(f"Download Python failed: {exc}")
            self.result_ready.emit(False, str(exc))

    def _download_verified(self, url: str, sha256: str, what: str) -> bytes | None:
        """Download *url*; emit a failure and return None unless its SHA-256 matches."""
        try:
            # Read at call time: the https guard lives in pip_installer.
            from Imervue.plugin import pip_installer
            req = Request(url, headers=_UA_HEADERS)
            with pip_installer._https_urlopen(req, timeout=120) as resp:
                data = resp.read()
        except OSError as e:
            self.result_ready.emit(False, f"Failed to download {what}: {e}")
            return None
        if not _matches_sha256(data, sha256):
            self.result_ready.emit(False, f"{what} does not match its checksum; not using it")
            return None
        return data

    def _download_embed_zip(self) -> bytes | None:
        self.log.emit(f"Downloading Python {_EMBED_PYTHON_VERSION} embeddable ...")
        return self._download_verified(
            _EMBED_PYTHON_URL, _EMBED_PYTHON_SHA256, f"Python {_EMBED_PYTHON_VERSION}")

    def _extract_safely(self, data: bytes, dest_dir: Path) -> bool:
        """Extract the embeddable zip to *dest_dir*, rejecting zip-slip entries."""
        self.log.emit("Extracting Python embeddable ...")
        dest_resolved = dest_dir.resolve()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.namelist():
                target = (dest_resolved / member).resolve()
                if not target.is_relative_to(dest_resolved):
                    self.result_ready.emit(
                        False, f"Refusing unsafe zip entry: {member}")
                    return False
            zf.extractall(dest_dir)
        return True

    def _patch_pth_files(self, dest_dir: Path) -> None:
        """Uncomment ``import site`` in python*._pth so pip can work."""
        dest_resolved = dest_dir.resolve()
        for pth_file in dest_dir.glob("python*._pth"):
            # glob("python*._pth") can only return names matching that literal
            # pattern, and the parent is dest_dir itself — still reject anything
            # that resolves outside dest_dir (e.g. a symlinked entry).
            resolved = pth_file.resolve()
            if not resolved.is_relative_to(dest_resolved):
                continue
            if pth_file.parent != dest_dir or not _PTH_NAME_RE.fullmatch(pth_file.name):
                continue
            safe_path = dest_dir / pth_file.name
            self.log.emit(f"Patching {safe_path.name} to enable 'import site' ...")
            content = safe_path.read_text(encoding="utf-8")
            safe_path.write_text(
                content.replace("#import site", "import site"),
                encoding="utf-8",
            )

    def _bootstrap_pip(self, dest_dir: Path, python_exe: Path) -> bool:
        """Install pip from its pinned, checksum-verified wheel; True on success."""
        self.log.emit(f"Downloading pip {_PIP_WHEEL_VERSION} ...")
        wheel_data = self._download_verified(
            _PIP_WHEEL_URL, _PIP_WHEEL_SHA256, f"pip {_PIP_WHEEL_VERSION}")
        if wheel_data is None:
            return False

        wheel_path = dest_dir / _PIP_WHEEL_NAME
        wheel_path.write_bytes(wheel_data)
        try:
            self.log.emit("Installing pip ...")
            returncode = self._run_with_live_output(
                [str(python_exe), "-c", _PIP_FROM_WHEEL, str(wheel_path)],
                cwd=str(dest_dir),
                timeout=300,
            )
            if returncode != 0:
                self.result_ready.emit(
                    False, f"pip installation failed (exit code {returncode})")
                return False
        finally:
            wheel_path.unlink(missing_ok=True)
        return True

    def _run_with_live_output(
        self, cmd: list[str], cwd: str | None = None, timeout: int = 600,
    ) -> int:
        """執行子程序並即時 emit 每一行輸出"""
        kw = _subprocess_kwargs()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            **kw,
        )
        self._proc = proc
        if self.isInterruptionRequested():
            terminate_process(proc)
        try:
            for line in proc.stdout:
                text = line.rstrip("\n\r")
                if text:
                    self.log.emit(text)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.log.emit(_PROCESS_TIMEOUT_MSG)
            return -1
        return proc.returncode
