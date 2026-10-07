"""Real QThreads cancel/retire without blocking dialogs or dropping live owners."""
from threading import Event
from time import perf_counter

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout
from shiboken6 import isValid

from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.plugin import worker_retirement
from Imervue.multi_language.language_wrapper import language_wrapper


class _BlockedWorker(QThread):
    result_ready = Signal()

    def __init__(self, *, parent=None, slow_stop=False, fail_stop=False):
        super().__init__(parent)
        self.entered, self.release, self.stopping = Event(), Event(), Event()
        self.slow_stop, self.fail_stop = slow_stop, fail_stop
        self.hook_threads = []

    def run(self):
        self.entered.set()
        self.release.wait(10)
        self.result_ready.emit()

    def stop(self):
        self.hook_threads.append(QThread.currentThread())
        self.stopping.set()
        if self.fail_stop:
            raise OSError("cannot terminate child")
        if self.slow_stop:
            self.release.wait(10)

    def abort(self):
        self.hook_threads.append(QThread.currentThread())


class _Dialog(WorkerHostMixin, QDialog):
    def __init__(self, *, slow_stop=False, fail_stop=False):
        super().__init__(None)
        QVBoxLayout(self)
        self._worker = _BlockedWorker(parent=self, slow_stop=slow_stop, fail_stop=fail_stop)
        self.results = []
        self._worker.result_ready.connect(lambda: self.results.append("late result"))


def _cleanup(dialog, workers, pump_until):
    for worker in workers:
        worker.release.set()
    assert pump_until(lambda: not worker_retirement._RETIRING)
    for worker in workers:
        if isValid(worker):
            assert worker.wait(10000)
    if isValid(dialog):
        dialog.deleteLater()


@pytest.mark.parametrize("finish", ["reject", "accept", "close", "done"])
def test_finish_returns_promptly_and_defers_result_until_exit(qapp, pump_until, finish):
    dialog = _Dialog()
    worker = dialog._worker
    ended = []
    dialog.finished.connect(ended.append)
    dialog.show()
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        begin = perf_counter()
        if finish == "done":
            dialog.done(7)
        else:
            getattr(dialog, finish)()
        assert (perf_counter() - begin) < 0.05
        assert not ended and not dialog.isEnabled()
        assert dialog._worker is None and dialog._worker_retiring
        assert language_wrapper.language_word_dict["worker_cancelling"] in dialog.windowTitle()
        assert worker.parent() is not dialog and worker.isRunning()
        dialog.accept()  # late success cannot turn a rejection into acceptance
        worker.release.set()
        assert pump_until(lambda: bool(ended))
        assert ended == [{"reject": 0, "close": 0, "accept": 1, "done": 7}[finish]]
        assert dialog.results == []
        assert dialog.isEnabled() and not dialog.isVisible()
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_blocking_cancel_hook_runs_off_ui_and_heartbeat_continues(qapp, pump_until):
    from PySide6.QtCore import QTimer
    dialog = _Dialog(slow_stop=True)
    worker = dialog._worker
    ticks = []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        dialog.reject()
        assert pump_until(worker.stopping.is_set)
        timer.start()
        assert pump_until(lambda: len(ticks) >= 3)
        assert dialog._worker_retiring and worker.isRunning()
        assert all(thread is not qapp.thread() for thread in worker.hook_threads)
        worker.release.set()
        assert pump_until(lambda: not dialog._worker_retiring)
    finally:
        timer.stop()
        _cleanup(dialog, [worker], pump_until)


def test_external_owner_deletion_does_not_delete_running_thread(qapp, pump_until):
    dialog = _Dialog()
    worker = dialog._worker
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        dialog.reject()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(dialog)
        assert isValid(worker) and worker.isRunning()
        worker.release.set()
        assert pump_until(lambda: not worker_retirement._RETIRING)
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_multiple_workers_and_failing_hook_still_join_all(qapp, pump_until, caplog):
    dialog = _Dialog(fail_stop=True)
    dialog._worker_attrs = ("_worker", "_aux")
    workers = [dialog._worker, _BlockedWorker(parent=dialog)]
    dialog._aux = workers[1]
    for worker in workers:
        worker.start()
    try:
        assert pump_until(lambda: all(w.entered.is_set() for w in workers))
        dialog.reject()
        assert pump_until(lambda: all(w.stopping.is_set() for w in workers))
        assert "Worker cancellation hook failed" in caplog.text
        workers[0].release.set()
        assert workers[1].isRunning() and dialog._worker_retiring
        workers[1].release.set()
        assert pump_until(lambda: not dialog._worker_retiring)
    finally:
        _cleanup(dialog, workers, pump_until)


def test_reopen_after_cancel_has_no_old_worker_results(qapp, pump_until):
    dialog = _Dialog()
    worker = dialog._worker
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        event = QCloseEvent()
        dialog.closeEvent(event)
        assert not event.isAccepted()
        worker.release.set()
        assert pump_until(lambda: not dialog._worker_retiring)
        dialog.show()
        new_worker = dialog._worker = _BlockedWorker(parent=dialog)
        new_worker.result_ready.connect(lambda: dialog.results.append("new result"))
        new_worker.start()
        try:
            assert pump_until(new_worker.entered.is_set)
            new_worker.release.set()
            assert pump_until(lambda: dialog.results == ["new result"])
            assert new_worker.wait(10000)
        finally:
            new_worker.release.set()
            assert new_worker.wait(10000)
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_already_queued_accept_does_not_override_cancel(qapp, pump_until):
    dialog = _Dialog()
    worker = dialog._worker
    worker.result_ready.connect(dialog.accept, Qt.ConnectionType.QueuedConnection)
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        worker.result_ready.emit()  # disconnect cannot remove this posted slot
        dialog.reject()
        assert pump_until(worker.stopping.is_set)
        assert dialog._worker_close_result == 0
        worker.release.set()
        assert pump_until(lambda: not dialog._worker_retiring)
        assert dialog.result() == 0
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_custom_done_finalization_does_not_wait_or_cancel_success(qapp, pump_until):
    from Imervue.gui._apply_save import finalize_worker
    dialog = _Dialog()
    worker = dialog._worker
    ended = []
    dialog.finished.connect(ended.append)
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        begin = perf_counter()
        finalize_worker(dialog)
        dialog.accept()
        assert perf_counter() - begin < 0.05
        assert dialog._worker_retiring and not ended
        assert not worker.stopping.is_set()
        worker.release.set()
        assert pump_until(lambda: ended == [1])
        assert worker.hook_threads == []
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_duplicate_attributes_cancel_same_worker_once(qapp, pump_until):
    dialog = _Dialog()
    worker = dialog._worker
    dialog._worker_attrs = ("_worker", "_aux")
    dialog._aux = worker
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        dialog.reject()
        worker.release.set()
        assert pump_until(lambda: not dialog._worker_retiring)
        assert len(worker.hook_threads) == 2  # one stop and one abort
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_finished_worker_finishes_dialog_immediately(qapp, pump_until):
    dialog = _Dialog()
    worker = dialog._worker
    worker.release.set()
    worker.start()
    try:
        assert worker.wait(10000)
        dialog.accept()
        assert dialog.result() == 1 and dialog._worker is None
        assert not getattr(dialog, "_worker_retiring", False)
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_tls_completion_is_polled_without_ui_join(qapp, monkeypatch):
    dialog = _Dialog()
    retirement = worker_retirement.WorkerRetirement(dialog, [], lambda: None)
    waits = []
    monkeypatch.setattr(retirement, "wait", lambda timeout: waits.append(timeout) or False)
    scheduled = []
    monkeypatch.setattr(worker_retirement, "call_later", lambda *args: scheduled.append(args))
    retirement._finish()
    assert waits == [0] and scheduled == [(10, retirement, retirement._finish)]
    retirement.deleteLater()
    dialog.deleteLater()


def test_final_event_loop_exit_joins_outstanding_reapers(monkeypatch):
    from types import SimpleNamespace
    calls = []
    fake = SimpleNamespace(wait=lambda: calls.append("join"))
    monkeypatch.setattr(worker_retirement, "_RETIRING", [fake])
    worker_retirement._drain_on_exit()
    assert calls == ["join"]


def test_modal_exec_remains_alive_for_cancel_then_worker_completion(qapp, pump_until):
    from Imervue.system.qt_timers import call_later
    dialog = _Dialog()
    worker = dialog._worker
    worker.start()
    try:
        assert pump_until(worker.entered.is_set)
        call_later(0, dialog, dialog.reject)
        call_later(30, dialog, worker.release.set)
        assert dialog.exec() == 0
        assert not dialog._worker_retiring
    finally:
        _cleanup(dialog, [worker], pump_until)


def test_completion_exception_still_releases_retirement(qapp):
    dialog = _Dialog()

    def failed():
        raise RuntimeError("failed UI completion")

    retirement = worker_retirement.WorkerRetirement(dialog, [], failed)
    worker_retirement._RETIRING.add(retirement)
    try:
        with pytest.raises(RuntimeError, match="failed UI completion"):
            retirement._finish()
        assert retirement not in worker_retirement._RETIRING
    finally:
        retirement.deleteLater()
        dialog.deleteLater()
