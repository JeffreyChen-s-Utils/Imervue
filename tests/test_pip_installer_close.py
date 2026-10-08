"""Dependency dialogs retain real workers without waiting on the UI thread."""
from threading import Event
from time import perf_counter

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QDialog

from Imervue.plugin.pip_installer import InstallDependenciesDialog


class Blocked(QThread):
    def __init__(self):
        super().__init__()
        self.entered, self.release = Event(), Event()
    def run(self):
        self.entered.set()
        self.release.wait(5)


def test_cancel_is_nonblocking_and_keeps_owner_until_exit(qapp, pump_until):
    dialog = InstallDependenciesDialog(None, [("optional", "optional-package")])
    worker = Blocked()
    dialog._find_worker = worker
    dialog.show()
    worker.start()
    try:
        assert worker.entered.wait(2)
        started = perf_counter()
        dialog.reject()
        assert perf_counter() - started < .1
        assert worker.isRunning() and not dialog.isEnabled() and dialog.isVisible()
        worker.release.set()
        pump_until(lambda: not dialog.isVisible())
        assert dialog.result() == QDialog.DialogCode.Rejected
    finally:
        worker.release.set()
        worker.wait()
        dialog.deleteLater()


def test_idle_close_completes_immediately(qapp):
    dialog = InstallDependenciesDialog(None, [])
    dialog.reject()
    assert not dialog.isVisible() and not getattr(dialog, "_worker_retiring", False)
    dialog.deleteLater()


def test_ready_callback_failure_remains_retryable(qapp, monkeypatch):
    from Imervue.plugin.pip_installer import _EnsureDepsHelper
    from Imervue.plugin.status import status_registry
    from PySide6.QtCore import QObject
    import pytest
    parent = QDialog()
    # Built without __init__, which would start a dependency check.
    helper = _EnsureDepsHelper.__new__(_EnsureDepsHelper)  # pylint: disable=no-value-for-parameter  # __new__ takes the class
    QObject.__init__(helper)
    helper._parent_widget, helper._status_key = parent, "test-callback"
    def fail():
        raise RuntimeError("model initialization failed")
    helper._on_ready = fail
    with pytest.raises(RuntimeError, match="model initialization" ):
        helper._ready()
    row = next(row for row in status_registry.snapshot() if row.key == "test-callback")
    assert row.status == "failed" and "model initialization failed" in row.reason
    helper._on_ready = lambda: None
    helper._ready()
    row = next(row for row in status_registry.snapshot() if row.key == "test-callback")
    assert row.status == "available"
    helper.deleteLater()
    parent.deleteLater()
