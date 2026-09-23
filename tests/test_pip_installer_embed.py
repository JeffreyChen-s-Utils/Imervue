"""The embeddable Python and its pip are only installed once their checksums match.

``_DownloadPythonWorker`` fetches CPython's embeddable zip and a pinned pip
wheel for plugins that need an interpreter with pip. Both are compared against
pinned SHA-256 digests before anything is extracted or run. The network, the
child process and the pip check are patched, so nothing is downloaded.
"""
from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from Imervue.plugin import pip_installer as pi


def _embed_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("python.exe", b"MZ fake interpreter")
        zf.writestr("python312._pth", "python312.zip\n.\n#import site\n")
    return buf.getvalue()


_ZIP = _embed_zip()
_WHEEL = b"fake pip wheel"


class _Resp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


@pytest.fixture
def worker(qapp, tmp_path, monkeypatch):
    """A worker wired to fakes; ``served`` maps a URL to the bytes it returns."""
    monkeypatch.setattr(pi, "_embedded_python_dir", lambda: tmp_path / "py")
    monkeypatch.setattr(pi, "_EMBED_PYTHON_SHA256", hashlib.sha256(_ZIP).hexdigest())
    monkeypatch.setattr(pi, "_PIP_WHEEL_SHA256", hashlib.sha256(_WHEEL).hexdigest())
    monkeypatch.setattr(pi, "_verify_python", lambda _exe: True)
    served = {pi._EMBED_PYTHON_URL: _ZIP, pi._PIP_WHEEL_URL: _WHEEL}
    monkeypatch.setattr(pi, "_https_urlopen", lambda req, timeout: _Resp(served[req.full_url]))
    w = pi._DownloadPythonWorker()
    w.commands = []

    def fake_run(cmd, cwd=None, timeout=None):
        w.commands.append(cmd)
        return 0

    w._run_with_live_output = fake_run
    w.results = []
    w.result_ready.connect(lambda ok, msg: w.results.append((ok, msg)))
    w.served = served
    w.dest = tmp_path / "py"
    return w


def test_pinned_digests_are_sha256():
    for digest in (pi._EMBED_PYTHON_SHA256, pi._PIP_WHEEL_SHA256):
        assert len(digest) == 64
        int(digest, 16)
    assert pi._PIP_WHEEL_NAME in pi._PIP_WHEEL_URL


def test_matches_sha256():
    assert pi._matches_sha256(b"abc", hashlib.sha256(b"abc").hexdigest())
    assert not pi._matches_sha256(b"abd", hashlib.sha256(b"abc").hexdigest())


def test_verified_downloads_install_pip_from_the_wheel(worker):
    worker.run()
    assert worker.results == [(True, str(worker.dest / "python.exe"))]
    (cmd,) = worker.commands
    assert cmd == [str(worker.dest / "python.exe"), "-c", pi._PIP_FROM_WHEEL,
                   str(worker.dest / pi._PIP_WHEEL_NAME)]
    assert not (worker.dest / pi._PIP_WHEEL_NAME).exists()   # wheel removed afterwards
    assert "import site" in (worker.dest / "python312._pth").read_text(encoding="utf-8")


def test_tampered_python_zip_is_refused_before_extraction(worker):
    worker.served[pi._EMBED_PYTHON_URL] = _embed_zip() + b"tampered"
    worker.run()
    (result,) = worker.results
    assert result[0] is False and "checksum" in result[1]
    assert not (worker.dest / "python.exe").exists()
    assert worker.commands == []


def test_tampered_pip_wheel_is_never_run(worker):
    worker.served[pi._PIP_WHEEL_URL] = b"tampered wheel"
    worker.run()
    (result,) = worker.results
    assert result[0] is False and "checksum" in result[1]
    assert worker.commands == []
    assert not (worker.dest / pi._PIP_WHEEL_NAME).exists()


def test_failed_pip_install_is_reported(worker):
    worker._run_with_live_output = lambda cmd, cwd=None, timeout=None: 3
    worker.run()
    assert worker.results == [(False, "pip installation failed (exit code 3)")]
