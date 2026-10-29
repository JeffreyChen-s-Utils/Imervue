"""
Background workers of the dependency installer and the package check.

* :func:`check_missing_packages` — which ``(import_name, pip_name)`` pairs are
  still missing (a file-system check in a frozen build, an import otherwise).
* ``_FindPythonWorker`` / ``_CheckDepsWorker`` / ``_ImportWorker`` — interpreter
  search, package check and post-install import off the UI thread.
* ``_InstallWorker`` — runs ``pip install`` per package under the constraints
  file and streams its output.

:mod:`Imervue.plugin.pip_installer` re-exports these names.
"""
from __future__ import annotations

import importlib
import logging
import subprocess
import sys
import tempfile
from threading import Event, Timer
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from Imervue.plugin.installation import resource_reservation
from Imervue.plugin.pip_constraints import install_command, write_constraints_file
from Imervue.plugin.pip_embed_python import _PROCESS_TIMEOUT_MSG
from Imervue.plugin.python_finder import _find_python, _subprocess_kwargs
from Imervue.plugin.subprocess_util import terminate_process
from Imervue.system.app_paths import is_frozen as _is_frozen

logger = logging.getLogger("Imervue.plugin.pip_installer")


# ===========================
# Python 搜尋
# ===========================

class _FindPythonWorker(QThread):
    """在背景執行緒搜尋可用的 Python 直譯器，避免阻塞 UI。"""
    result_ready = Signal(object)  # str | None

    def run(self):
        try:
            result = _find_python()
        except Exception as exc:  # worker must always report
            # Registry / filesystem probes (e.g. iterdir on a locked dir) can
            # raise; without this result_ready never fires and the install dialog
            # hangs with its progress bar spinning. Report "no Python found".
            logger.exception("Python search failed: %s", exc)
            result = None
        self.result_ready.emit(result)


# ===========================
# 套件檢查
# ===========================

def check_missing_packages(
    packages: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """回傳缺少的套件列表。

    Args:
        packages: [(import_name, pip_name), ...]

    Returns:
        Still-missing subset of *packages*.
    """
    # 凍結環境下，在背景執行緒 import 含 native DLL 的套件（如 onnxruntime）
    # 會導致 segfault。改用檔案系統檢查是否已安裝。
    if _is_frozen():
        return _check_missing_frozen(packages)

    missing = []
    for import_name, pip_name in packages:
        try:
            logger.info("check_missing_packages: trying import '%s'", import_name)
            importlib.import_module(import_name)
            logger.info("check_missing_packages: '%s' OK", import_name)
        # An optional package's import runs its native init (DLL loads, CUDA
        # probes), which can raise anything; every failure means "missing".
        except Exception as e:  # noqa: BLE001 - any import failure means "missing"
            logger.info(
                "check_missing_packages: '%s' missing (%s: %s)",
                import_name, type(e).__name__, e,
            )
            missing.append((import_name, pip_name))
    return missing


def _check_missing_frozen(
    packages: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """凍結環境：透過檔案系統檢查套件是否存在（不 import，避免 DLL 崩潰）。"""
    from Imervue.system.app_paths import frozen_site_packages as _frozen_site_packages
    target_dir = _frozen_site_packages()
    logger.info(
        "_check_missing_frozen: checking in %s (exists=%s)",
        target_dir, target_dir.is_dir(),
    )

    missing = []
    for import_name, pip_name in packages:
        # 套件可能是目錄（package）或單一 .py 檔
        pkg_dir = target_dir / import_name
        pkg_file = target_dir / (import_name + ".py")
        # 也檢查 .dist-info 目錄（pip 安裝後一定會有）
        found = pkg_dir.is_dir() or pkg_file.is_file()
        logger.info("_check_missing_frozen: '%s' → dir=%s, file=%s, found=%s",
                     import_name, pkg_dir.is_dir(), pkg_file.is_file(), found)
        if not found:
            missing.append((import_name, pip_name))
    return missing


class _CheckDepsWorker(QThread):
    """在背景執行緒檢查套件是否已安裝（import 大型套件如 onnxruntime 很慢）。"""
    result_ready = Signal(list)  # list[tuple[str, str]]  missing packages

    def __init__(self, packages: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._packages = packages
        logger.info("_CheckDepsWorker created for packages: %s", packages)

    def run(self):
        logger.info("_CheckDepsWorker.run() started")
        try:
            result = check_missing_packages(self._packages)
            logger.info("_CheckDepsWorker.run() check done, missing=%s", result)
        except Exception:
            logger.exception("_CheckDepsWorker.run() exception")
            result = list(self._packages)
        logger.info("_CheckDepsWorker.run() emitting result_ready")
        self.result_ready.emit(result)
        logger.info("_CheckDepsWorker.run() done")


class _ImportWorker(QThread):
    """在背景執行緒 import 剛安裝好的套件（避免阻塞 UI）。"""
    result_ready = Signal()

    def __init__(self, import_names: list[str]):
        super().__init__()
        self._names = import_names

    error = Signal(str)

    def run(self):
        errors = []
        for name in self._names:
            try:
                importlib.import_module(name)
            except Exception as exc:
                logger.exception("Installed dependency %s cannot import", name)
                errors.append(f"{name}: {exc or type(exc).__name__}")
        if errors:
            self.error.emit("; ".join(errors))
        else:
            self.result_ready.emit()


# ===========================
# 安裝 Worker
# ===========================

class _InstallWorker(QThread):
    """背景安裝缺少的 pip 套件（即時輸出每行 log）"""
    log = Signal(str)
    result_ready = Signal(bool, str)  # success, message

    def __init__(self, pip_names: list[str], python_path: str):
        super().__init__()
        self._pip_names = pip_names
        self._python = python_path
        self._proc = None

    def run(self):
        extra_args = self._frozen_target_args()
        try:
            with tempfile.TemporaryDirectory(
                    prefix="imervue_pip_", ignore_cleanup_errors=True) as tmp:
                constraints = write_constraints_file(Path(tmp))
                with resource_reservation("pip:" + str(Path(self._python).resolve())):
                    ok, message = self._install_all(constraints, extra_args)
        except OSError as exc:
            ok, message = False, str(exc)
        except Exception as exc:  # a worker must always report
            logger.exception("Installing packages failed")
            ok, message = False, str(exc)
        self.result_ready.emit(ok, message)

    def _frozen_target_args(self) -> list[str]:
        """Return ``--target`` args for a frozen build (creating the dir), else none."""
        if not _is_frozen():
            return []
        from Imervue.system.app_paths import frozen_site_packages as _frozen_site_packages
        target_dir = str(_frozen_site_packages())
        self.log.emit(f"Frozen mode: installing to {target_dir}")
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        if target_dir not in sys.path:
            sys.path.insert(0, target_dir)
        return ["--target", target_dir]

    def _install_all(self, constraints: Path, extra_args: list[str]) -> tuple[bool, str]:
        """Install every package in turn under *constraints*; stop at the first failure."""
        for name in self._pip_names:
            if self.isInterruptionRequested():
                return False, "Dependency installation cancelled"
            self.log.emit(f"Installing {name} ...")
            cmd = install_command(self._python, name, constraints, extra_args)
            try:
                returncode = self._run_with_live_output(cmd, timeout=600)
            except FileNotFoundError:
                return False, f"Python not found: {self._python}"
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                return False, str(exc)
            except Exception as exc:
                # Worker boundary: the dialog waits on result_ready, so even a
                # bug must be reported rather than escape the thread.
                logger.exception("Installing %s failed unexpectedly", name)
                return False, str(exc)
            if returncode != 0:
                return False, f"Failed to install {name} (exit code {returncode})"
        return True, "All packages installed successfully!"

    def _run_with_live_output(self, cmd: list[str], timeout: int = 600) -> int:
        """執行子程序並即時 emit 每一行輸出"""
        kw = _subprocess_kwargs()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kw,
        )
        self._proc = proc
        expired = Event()

        def expire() -> None:
            expired.set()
            terminate_process(proc)

        deadline = Timer(timeout, expire)
        deadline.daemon = True
        deadline.start()
        try:
            if self.isInterruptionRequested():
                return -1
            for line in proc.stdout:
                text = line.rstrip("\n\r")
                if text:
                    self.log.emit(text)
            proc.wait()
            if expired.is_set():
                self.log.emit(_PROCESS_TIMEOUT_MSG)
                return -1
            return -1 if self.isInterruptionRequested() else proc.returncode
        finally:
            deadline.cancel()
            terminate_process(proc)
            deadline.join()
            proc.stdout.close()
            self._proc = None

    def stop(self) -> None:
        """Reap the pip child off the UI thread when its host is closing."""
        self.requestInterruption()
        terminate_process(self._proc)
