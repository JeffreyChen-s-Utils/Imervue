"""Contracts of the plugin dependency installer that other tests leave open.

``pip_installer`` is the public import location for the dependency gate, its
dialog and its workers, wherever their code lives. These tests patch each
collaborator on the module that actually owns the code under test (found from
the object's ``__module__``), so they pin behaviour, not file layout.
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import zipfile

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog

from Imervue.plugin import pip_installer as pi
from Imervue.plugin.status import status_registry


def _owner(obj):
    """The module whose globals *obj*'s code reads."""
    return sys.modules[obj.__module__]


def _status(key: str):
    return next(row for row in status_registry.snapshot() if row.key == key)


# ---------------------------------------------------------------------------
# Public import location
# ---------------------------------------------------------------------------

_PUBLIC_NAMES = (
    "ensure_dependencies", "register_translations", "_TRANSLATIONS",
    "InstallDependenciesDialog", "_EnsureDepsHelper", "_CheckDepsWorker",
    "_ImportWorker", "_InstallWorker", "_FindPythonWorker", "_DownloadPythonWorker",
    "check_missing_packages", "_check_missing_frozen", "_matches_sha256",
    "_https_urlopen", "_EMBED_PYTHON_VERSION", "_EMBED_PYTHON_URL",
    "_EMBED_PYTHON_SHA256", "_PIP_WHEEL_VERSION", "_PIP_WHEEL_NAME", "_PIP_WHEEL_URL",
    "_PIP_WHEEL_SHA256", "_PIP_FROM_WHEEL", "_USER_AGENT", "_UA_HEADERS",
    "_PROCESS_TIMEOUT_MSG", "_PTH_NAME_RE", "_find_python", "_subprocess_kwargs",
    "_verify_python", "_is_frozen", "_embedded_python_dir", "_embedded_python_exe",
    "_PYTHON_EXE_NAME", "_VERIFY_TIMEOUT_S", "logger",
)


@pytest.mark.parametrize("name", _PUBLIC_NAMES)
def test_names_stay_importable_from_pip_installer(name):
    assert hasattr(pi, name)


def test_https_guard_lives_in_pip_installer():
    assert pi._https_urlopen.__module__ == "Imervue.plugin.pip_installer"


def test_moved_code_logs_under_the_installer_logger():
    for obj in (pi.check_missing_packages, pi._InstallWorker, pi._DownloadPythonWorker,
                pi.InstallDependenciesDialog, pi._EnsureDepsHelper):
        assert _owner(obj).logger.name == "Imervue.plugin.pip_installer"


def test_ensure_dependencies_builds_the_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(_owner(pi.ensure_dependencies), "_EnsureDepsHelper",
                        lambda *args: calls.append(args))
    pi.ensure_dependencies("parent", [("a", "b")], "cb")
    assert calls == [("parent", [("a", "b")], "cb")]


# ---------------------------------------------------------------------------
# Package checks
# ---------------------------------------------------------------------------


def test_frozen_check_looks_at_the_site_packages_dir(monkeypatch, tmp_path):
    from Imervue.system import app_paths
    (tmp_path / "pkg_dir").mkdir()
    (tmp_path / "single.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(_owner(pi.check_missing_packages), "_is_frozen", lambda: True)
    monkeypatch.setattr(app_paths, "frozen_site_packages", lambda: tmp_path)
    packages = [("pkg_dir", "pkg-dir"), ("single", "single"), ("absent", "absent-pip")]
    assert pi.check_missing_packages(packages) == [("absent", "absent-pip")]


def test_frozen_check_with_no_packages_is_empty(monkeypatch, tmp_path):
    from Imervue.system import app_paths
    monkeypatch.setattr(app_paths, "frozen_site_packages", lambda: tmp_path / "none")
    assert pi._check_missing_frozen([]) == []


def test_check_worker_reports_everything_missing_when_the_check_fails(qapp, monkeypatch):
    def boom(_packages):
        raise RuntimeError("check broke")
    monkeypatch.setattr(_owner(pi._CheckDepsWorker), "check_missing_packages", boom)
    worker = pi._CheckDepsWorker([("a", "a-pip")])
    results = []
    worker.result_ready.connect(results.append)
    worker.run()
    assert results == [[("a", "a-pip")]]
    worker.deleteLater()


def test_import_worker_success_emits_ready(qapp, monkeypatch):
    monkeypatch.setattr(_owner(pi._ImportWorker).importlib, "import_module", lambda _n: None)
    worker = pi._ImportWorker(["x"])
    done, errors = [], []
    worker.result_ready.connect(lambda: done.append(True))
    worker.error.connect(errors.append)
    worker.run()
    assert done == [True] and errors == []
    worker.deleteLater()


def test_import_worker_reports_an_exception_without_a_message(qapp, monkeypatch):
    def boom(_name):
        raise RuntimeError
    monkeypatch.setattr(_owner(pi._ImportWorker).importlib, "import_module", boom)
    worker = pi._ImportWorker(["x"])
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    # An exception object is always truthy, so the empty message is kept as is.
    assert errors == ["x: "]
    worker.deleteLater()


# ---------------------------------------------------------------------------
# Install worker
# ---------------------------------------------------------------------------


def test_install_worker_stops_when_interrupted(qapp, monkeypatch):
    monkeypatch.setattr(_owner(pi._InstallWorker), "_is_frozen", lambda: False)
    worker = pi._InstallWorker(["a"], "python.exe")
    worker.isInterruptionRequested = lambda: True
    results = []
    worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert results == [(False, "Dependency installation cancelled")]
    worker.deleteLater()


def test_install_worker_stop_reaps_the_child(qapp, monkeypatch):
    reaped = []
    monkeypatch.setattr(_owner(pi._InstallWorker), "terminate_process", reaped.append)
    worker = pi._InstallWorker(["a"], "python.exe")
    worker._proc = "child"
    worker.stop()
    assert reaped == ["child"]
    worker.deleteLater()


class _FakeProc:
    def __init__(self, lines, *, time_out=False, returncode=0):
        self.stdout = iter(lines)
        self.returncode = returncode
        self._time_out = time_out
        self.waits = []
        self.killed = False

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self._time_out and len(self.waits) == 1:
            raise subprocess.TimeoutExpired("pip", timeout)
        return self.returncode

    def kill(self):
        self.killed = True


@pytest.fixture
def fake_popen(monkeypatch):
    """Replace ``subprocess.Popen``; ``fake_popen.proc`` is what it returns."""
    class _Factory:
        proc = None
        calls = []

        def __call__(self, cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            return self.proc

    factory = _Factory()
    factory.calls = []
    monkeypatch.setattr(subprocess, "Popen", factory)
    return factory


def test_install_worker_streams_non_blank_lines(qapp, fake_popen):
    fake_popen.proc = _FakeProc(["one\n", "\n", "two\r\n"], returncode=4)
    worker = pi._InstallWorker([], "python.exe")
    logs = []
    worker.log.connect(logs.append)
    assert worker._run_with_live_output(["pip"], timeout=7) == 4
    assert logs == ["one", "two"]
    ((cmd, kwargs),) = fake_popen.calls
    assert cmd == ["pip"] and "cwd" not in kwargs
    assert kwargs["stdout"] is subprocess.PIPE and kwargs["stderr"] is subprocess.STDOUT
    assert fake_popen.proc.waits == [7]
    worker.deleteLater()


def test_install_worker_kills_a_timed_out_child(qapp, fake_popen):
    fake_popen.proc = _FakeProc([], time_out=True)
    worker = pi._InstallWorker([], "python.exe")
    logs = []
    worker.log.connect(logs.append)
    assert worker._run_with_live_output(["pip"]) == -1
    assert fake_popen.proc.killed and fake_popen.proc.waits == [600, None]
    assert logs == ["Process timed out"]
    worker.deleteLater()


# ---------------------------------------------------------------------------
# Embedded Python download
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def download(qapp, tmp_path, monkeypatch):
    """Run a download worker over a served zip; return (worker, results)."""
    owner = _owner(pi._DownloadPythonWorker)

    def _run(zip_bytes, *, verify=True, urlopen=None):
        monkeypatch.setattr(owner, "_embedded_python_dir", lambda: tmp_path / "py")
        monkeypatch.setattr(owner, "_EMBED_PYTHON_SHA256",
                            hashlib.sha256(zip_bytes).hexdigest())
        monkeypatch.setattr(owner, "_PIP_WHEEL_SHA256", hashlib.sha256(b"whl").hexdigest())
        monkeypatch.setattr(owner, "_verify_python", lambda _exe: verify)
        served = {pi._EMBED_PYTHON_URL: zip_bytes, pi._PIP_WHEEL_URL: b"whl"}
        monkeypatch.setattr(pi, "_https_urlopen", urlopen or (
            lambda req, timeout: _Resp(served[req.full_url])))
        worker = pi._DownloadPythonWorker()
        worker._run_with_live_output = lambda cmd, cwd=None, timeout=None: 0
        results = []
        worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
        worker.run()
        worker.deleteLater()
        return results

    return _run


def test_zip_slip_entry_is_refused(download, tmp_path):
    results = download(_zip({"../evil.txt": b"x", "python.exe": b"MZ"}))
    assert results == [(False, "Refusing unsafe zip entry: ../evil.txt")]
    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "py" / "python.exe").exists()


def test_zip_without_the_interpreter_is_reported(download):
    results = download(_zip({"readme.txt": b"x"}))
    assert results == [(False, "python.exe not found after extraction")]


def test_failed_pip_verification_is_reported(download):
    results = download(_zip({"python.exe": b"MZ"}), verify=False)
    assert results == [(False, "pip verification failed after bootstrap")]


def test_download_network_error_is_reported(download):
    def offline(_req, timeout):
        raise OSError("offline")
    results = download(_zip({"python.exe": b"MZ"}), urlopen=offline)
    assert results == [(False, f"Failed to download Python {pi._EMBED_PYTHON_VERSION}: offline")]


def test_download_requests_carry_the_user_agent_and_timeout(download):
    seen = []
    zip_bytes = _zip({"python.exe": b"MZ"})
    served = {pi._EMBED_PYTHON_URL: zip_bytes, pi._PIP_WHEEL_URL: b"whl"}

    def record(req, timeout):
        seen.append((req.full_url, req.get_header("User-agent"), timeout))
        return _Resp(served[req.full_url])

    results = download(zip_bytes, urlopen=record)
    assert results[0][0] is True
    assert seen == [(pi._EMBED_PYTHON_URL, pi._USER_AGENT, 120),
                    (pi._PIP_WHEEL_URL, pi._USER_AGENT, 120)]


def test_unexpected_download_error_is_reported(download):
    def bug(_req, timeout):
        raise RuntimeError("bug")
    results = download(_zip({"python.exe": b"MZ"}), urlopen=bug)
    assert results == [(False, "bug")]


def test_pth_patch_skips_names_outside_the_pattern(qapp, tmp_path):
    (tmp_path / "python312._pth").write_text("#import site\n", encoding="utf-8")
    (tmp_path / "pythonX._pth").write_text("#import site\n", encoding="utf-8")
    worker = pi._DownloadPythonWorker()
    worker._patch_pth_files(tmp_path)
    assert (tmp_path / "python312._pth").read_text(encoding="utf-8") == "import site\n"
    assert (tmp_path / "pythonX._pth").read_text(encoding="utf-8") == "#import site\n"
    worker.deleteLater()


def test_download_worker_streams_output_and_honours_cwd(qapp, fake_popen):
    fake_popen.proc = _FakeProc(["a\n", "b\n"], returncode=0)
    worker = pi._DownloadPythonWorker()
    logs = []
    worker.log.connect(logs.append)
    assert worker._run_with_live_output(["py"], cwd="d", timeout=9) == 0
    assert logs == ["a", "b"] and worker._proc is fake_popen.proc
    ((_cmd, kwargs),) = fake_popen.calls
    assert kwargs["cwd"] == "d" and fake_popen.proc.waits == [9]
    worker.deleteLater()


def test_download_worker_kills_a_timed_out_child(qapp, fake_popen):
    fake_popen.proc = _FakeProc([], time_out=True)
    worker = pi._DownloadPythonWorker()
    logs = []
    worker.log.connect(logs.append)
    assert worker._run_with_live_output(["py"]) == -1
    assert fake_popen.proc.killed and logs == ["Process timed out"]
    worker.deleteLater()


# ---------------------------------------------------------------------------
# Install dialog
# ---------------------------------------------------------------------------


@pytest.fixture
def dialog(qapp):
    dlg = pi.InstallDependenciesDialog(None, [("mod_a", "pip-a"), ("mod_b", "pip-b")])
    yield dlg
    dlg.deleteLater()


def test_dialog_lists_the_missing_pip_names(dialog):
    assert dialog._status_key == "dependencies:mod_a,mod_b"
    assert _status(dialog._status_key).status == "missing"
    assert _status(dialog._status_key).reason == "pip-a, pip-b"


def test_no_python_off_windows_shows_the_error(dialog, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    dialog._install_btn.setEnabled(False)
    dialog._on_python_found(None)
    assert dialog._install_btn.isEnabled()
    assert "Python not found" in dialog._status.text()
    assert _status(dialog._status_key).status == "failed"


def test_no_python_on_windows_starts_the_download(dialog, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    started = []
    dialog._start_python_download = lambda: started.append(True)
    dialog._on_python_found(None)
    assert started == [True]


def test_found_python_starts_the_install(dialog):
    started = []
    dialog._start_package_install = started.append
    dialog._on_python_found("C:/py.exe")
    assert started == ["C:/py.exe"]


def test_failed_python_download_is_reported(dialog):
    dialog._on_python_downloaded(False, "no network")
    assert _status(dialog._status_key).status == "failed"
    assert _status(dialog._status_key).reason == "no network"
    assert "Failed to download Python: no network" in dialog._log.toPlainText()


def test_install_failure_is_shown(dialog):
    dialog._on_finished(False, "x" * 150)
    assert dialog._status.text() == "Error: " + "x" * 100
    assert dialog._install_btn.isEnabled()
    assert _status(dialog._status_key).status == "failed"


def test_install_success_when_frozen_finishes_on_the_ui_thread(dialog, monkeypatch):
    monkeypatch.setattr(_owner(pi.InstallDependenciesDialog), "_is_frozen", lambda: True)
    called = []
    dialog._on_success = lambda: called.append(True)
    dialog._on_finished(True, "done")
    assert called == [True]
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert _status(dialog._status_key).status == "available"


def test_install_success_imports_in_a_worker(dialog, monkeypatch):
    built = []

    class _FakeImport(QObject):
        from PySide6.QtCore import Signal
        result_ready = Signal()
        error = Signal(str)
        finished = Signal()

        def __init__(self, names):
            super().__init__()
            built.append(names)

        def start(self):
            built.append("started")

    monkeypatch.setattr(_owner(pi.InstallDependenciesDialog), "_is_frozen", lambda: False)
    monkeypatch.setattr(_owner(pi.InstallDependenciesDialog), "_ImportWorker", _FakeImport)
    dialog._on_finished(True, "done")
    assert built == [["mod_a", "mod_b"], "started"]
    dialog._import_worker.error.emit("mod_a: broken")
    assert dialog._status.text() == "mod_a: broken"
    assert _status(dialog._status_key).status == "failed"


def test_ready_callback_failure_keeps_the_dialog_open(dialog):
    def fail():
        raise RuntimeError
    dialog._on_success = fail
    dialog._on_import_done()
    assert dialog._status.text() == "RuntimeError"
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_log_line_updates_the_status(dialog):
    dialog._on_log("first line " + "y" * 100 + "\nsecond")
    assert dialog._status.text() == ("first line " + "y" * 100)[:80]
    assert _status(dialog._status_key).status == "running"


def test_reject_when_idle_publishes_cancelled(dialog):
    dialog.reject()
    assert _status(dialog._status_key).status == "cancelled"


# ---------------------------------------------------------------------------
# ensure_dependencies helper
# ---------------------------------------------------------------------------


@pytest.fixture
def helper(qapp):
    parent = QDialog()
    h = pi._EnsureDepsHelper.__new__(pi._EnsureDepsHelper)  # pylint: disable=no-value-for-parameter  # __new__ takes the class
    QObject.__init__(h)
    h._parent_widget, h._status_key = parent, "contract-helper"
    h.ready_calls = []
    h._on_ready = lambda: h.ready_calls.append(True)
    yield h
    h.deleteLater()
    parent.deleteLater()


def test_nothing_missing_calls_ready(helper):
    helper._handle_result([])
    assert helper.ready_calls == [True]
    assert _status("contract-helper").status == "available"


def test_missing_packages_open_the_dialog(helper, monkeypatch):
    opened = []

    class _FakeDialog:
        def __init__(self, parent, missing, on_success=None):
            opened.append((parent, missing, on_success))

        def setAttribute(self, *_a):
            opened.append("attr")

        def open(self):
            opened.append("open")

    monkeypatch.setattr(_owner(pi._EnsureDepsHelper), "InstallDependenciesDialog", _FakeDialog)
    helper._handle_result([("m", "m-pip")])
    assert opened[0][:2] == (helper._parent_widget, [("m", "m-pip")])
    assert opened[1:] == ["attr", "open"]
    assert _status("contract-helper").status == "missing"
    assert _status("contract-helper").reason == "m-pip"


def test_deleted_parent_cancels(helper, monkeypatch):
    monkeypatch.setattr(_owner(pi._EnsureDepsHelper), "isValid", lambda _w: False)
    helper._handle_result([])
    assert helper.ready_calls == []
    assert _status("contract-helper").status == "cancelled"
