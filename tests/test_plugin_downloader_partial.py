"""A failed plugin download must not leave a partial dir that reports 'Installed'.

The worker now downloads into a temp dir and swaps it into place only once every
file lands; a mid-download failure cleans up and leaves any existing install
untouched.
"""
from __future__ import annotations

from Imervue.plugin import plugin_downloader as pd


class _FakeResp:
    def __init__(self, data: bytes = b"content"):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _worker():
    return pd.DownloadPluginWorker("myplugin", [
        {"download_url": "https://x/a", "name": "__init__.py"},
        {"download_url": "https://x/b", "name": "b.py"},
    ])


def test_partial_download_leaves_no_plugin_dir(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    calls = [0]

    def fake_urlopen(_req, timeout=30):
        calls[0] += 1
        if calls[0] == 1:
            return _FakeResp(b"file1")
        raise RuntimeError("network drop mid-download")

    monkeypatch.setattr(pd, "_https_urlopen", fake_urlopen)
    errors: list = []
    worker = _worker()
    worker.error.connect(errors.append)
    worker.run()
    assert errors                                        # failure reported
    assert not (tmp_path / "myplugin").exists()          # no half-written plugin
    assert not (tmp_path / ".myplugin.partial").exists()  # temp cleaned up


def test_successful_download_installs_every_file(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    monkeypatch.setattr(pd, "_https_urlopen", lambda _req, timeout=30: _FakeResp())
    done: list = []
    worker = _worker()
    worker.result_ready.connect(done.append)
    worker.run()
    assert done == ["myplugin"]
    assert (tmp_path / "myplugin" / "__init__.py").read_bytes() == b"content"
    assert (tmp_path / "myplugin" / "b.py").exists()
    assert not (tmp_path / ".myplugin.partial").exists()
