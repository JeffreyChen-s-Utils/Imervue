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


def _run_failing(tmp_path, monkeypatch, caplog, exc):
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)

    def fake_urlopen(_req, timeout=30):
        raise exc

    monkeypatch.setattr(pd, "_https_urlopen", fake_urlopen)
    errors: list = []
    worker = _worker()
    worker.error.connect(errors.append)
    with caplog.at_level("DEBUG", logger="Imervue"):
        worker.run()
    return errors, [r for r in caplog.records if r.exc_info]


def test_network_error_is_reported_without_traceback(qapp, tmp_path, monkeypatch, caplog):
    errors, tracebacks = _run_failing(tmp_path, monkeypatch, caplog, OSError("offline"))
    assert errors == ["offline"]
    assert tracebacks == []
    assert not (tmp_path / ".myplugin.partial").exists()


def test_unexpected_error_is_reported_with_traceback(qapp, tmp_path, monkeypatch, caplog):
    errors, tracebacks = _run_failing(tmp_path, monkeypatch, caplog, RuntimeError("bug"))
    assert errors == ["bug"]
    (record,) = tracebacks
    assert record.exc_info[0] is RuntimeError and "myplugin" in record.getMessage()
    assert not (tmp_path / ".myplugin.partial").exists()


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


def _refused(qapp, tmp_path, monkeypatch, plugin_name, file_name):
    """Run a download whose names are unsafe; return (errors, urlopen calls)."""
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path / "plugins")
    calls: list = []
    monkeypatch.setattr(pd, "_https_urlopen", lambda req, timeout=30: calls.append(req))
    errors: list = []
    worker = pd.DownloadPluginWorker(plugin_name, [
        {"download_url": "https://x/a", "name": file_name},
    ])
    worker.error.connect(errors.append)
    worker.run()
    return errors, calls


def test_unsafe_plugin_name_is_refused_before_anything_is_touched(qapp, tmp_path, monkeypatch):
    victim = tmp_path / "keep.txt"
    victim.write_text("do not delete", encoding="utf-8")
    errors, calls = _refused(qapp, tmp_path, monkeypatch, "..", "__init__.py")
    assert errors and "unsafe" in errors[0]
    assert calls == []
    assert victim.read_text(encoding="utf-8") == "do not delete"


def test_unsafe_file_name_is_refused(qapp, tmp_path, monkeypatch):
    errors, calls = _refused(qapp, tmp_path, monkeypatch, "myplugin", "..\\..\\evil.py")
    assert errors and "unsafe" in errors[0]
    assert calls == []
    assert not (tmp_path / "evil.py").exists()


def _manifest_download(tmp_path, monkeypatch, manifest: bytes):
    """Download a plugin whose plugin.json says *manifest* over an installed copy."""
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    installed = tmp_path / "myplugin"
    installed.mkdir()
    (installed / "__init__.py").write_bytes(b"working copy")
    files = {"https://x/a": b"new", "https://x/m": manifest}
    monkeypatch.setattr(pd, "_https_urlopen", lambda req, timeout=30: _FakeResp(files[req.full_url]))
    errors: list = []
    done: list = []
    worker = pd.DownloadPluginWorker("myplugin", [
        {"download_url": "https://x/a", "name": "__init__.py"},
        {"download_url": "https://x/m", "name": "plugin.json"},
    ])
    worker.error.connect(errors.append)
    worker.result_ready.connect(done.append)
    worker.run()
    return errors, done, installed


def test_a_plugin_needing_a_newer_imervue_is_refused_and_the_install_kept(qapp, tmp_path, monkeypatch):
    from Imervue.plugin.plugin_api import PLUGIN_API_VERSION
    needed = PLUGIN_API_VERSION + 1
    errors, done, installed = _manifest_download(
        tmp_path, monkeypatch, f'{{"min_api_version": {needed}}}'.encode())
    assert done == []
    (error,) = errors
    assert "myplugin" in error and f"plugin API {needed}" in error and "Update Imervue" in error
    assert (installed / "__init__.py").read_bytes() == b"working copy"
    assert not (installed / "plugin.json").exists()
    assert not (tmp_path / ".myplugin.partial").exists()


def test_a_plugin_this_imervue_supports_installs(qapp, tmp_path, monkeypatch):
    errors, done, installed = _manifest_download(tmp_path, monkeypatch, b'{"min_api_version": 2}')
    assert (errors, done) == ([], ["myplugin"])
    assert (installed / "__init__.py").read_bytes() == b"new"


def test_a_plugin_with_a_broken_manifest_is_refused(qapp, tmp_path, monkeypatch):
    errors, done, installed = _manifest_download(tmp_path, monkeypatch, b"{broken")
    assert done == [] and len(errors) == 1
    assert (installed / "__init__.py").read_bytes() == b"working copy"


def test_same_plugin_concurrent_download_cannot_clobber_stage(qapp, tmp_path, monkeypatch):
    from threading import Event
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    entered, release = Event(), Event()
    def blocked(_request, timeout=30):
        entered.set()
        release.wait(5)
        return _FakeResp(b"working code")
    monkeypatch.setattr(pd, "_https_urlopen", blocked)
    first, second = _worker(), _worker()
    errors = []
    second.error.connect(errors.append)
    first.start()
    try:
        assert entered.wait(2)
        second.run()
        assert errors and "in progress" in errors[0]
        release.set()
        assert first.wait(3000)
        assert (tmp_path / "myplugin" / "__init__.py").read_bytes() == b"working code"
        assert list(tmp_path.iterdir()) == [tmp_path / "myplugin"]
        assert first.job_state.snapshot().status == "succeeded"
        assert second.job_state.snapshot().status == "failed"
    finally:
        release.set()
        first.wait()
        first.deleteLater()
        second.deleteLater()
