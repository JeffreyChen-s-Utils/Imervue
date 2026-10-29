"""Pin the background-jobs registry and panel row behaviour across module splits."""

from threading import Event

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThread, Qt
from shiboken6 import isValid

from Imervue.gui import background_jobs
from Imervue.gui.background_jobs import (
    BackgroundJobsDialog,
    Job,
    JobRegistry,
    open_background_jobs,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.job_state import JobState


class IdleWorker(QThread):
    """A worker whose run returns at once; the test controls its job state."""

    def __init__(self, paths=("a",)):
        super().__init__()
        self.job_state = JobState(list(paths))

    def run(self):
        """Return at once instead of entering QThread's default event loop."""


class GatedWorker(QThread):
    """A worker that blocks until released, then records its single source."""

    def __init__(self, release):
        super().__init__()
        self.release = release
        self.entered = Event()
        self.job_state = JobState(["a"])

    def run(self):
        self.entered.set()
        self.release.wait(5)
        self.job_state.record("a", output="result")
        self.job_state.finish()


def _word(key, fallback):
    return language_wrapper.language_word_dict.get(key, fallback)


def _failed_worker(paths=("a", "b")):
    worker = IdleWorker(paths)
    worker.job_state.record(paths[0], output="out-a.png")
    worker.job_state.record(paths[1], error="broken")
    worker.job_state.finish()
    return worker


@pytest.fixture
def registry(qapp):
    value = JobRegistry()
    yield value
    value.drain()
    value.poll()
    value.deleteLater()


@pytest.fixture
def panel(registry):
    dialog = BackgroundJobsDialog(None, registry=registry)
    yield dialog
    dialog.deleteLater()


def test_add_rejects_non_thread_and_thread_without_state(registry):
    with pytest.raises(TypeError, match="requires a QThread with JobState"):
        registry.add(object(), "bad")
    with pytest.raises(TypeError, match="requires a QThread with JobState"):
        registry.add(QThread(), "bad")
    assert registry.jobs == []


def test_add_completed_rejects_non_state(registry):
    with pytest.raises(ValueError, match="terminal JobState"):
        registry.add_completed("x", object())


def test_add_registers_job_starts_timer_and_emits(registry):
    seen = []
    registry.changed.connect(lambda: seen.append(1))
    worker = IdleWorker()
    job = registry.add(worker, "title", owned=True)
    assert isinstance(job, Job)
    assert (job.title, job.state, job.worker, job.owned) == ("title", worker.job_state, worker, True)
    assert job.retry_factory is None and not job.retry_started and not job.settled
    assert registry._timer.isActive() and seen == [1]


def test_poll_settles_terminal_unstarted_worker_and_stops_timer(registry):
    worker = IdleWorker()
    worker.job_state.finish()
    job = registry.add(worker, "done")
    seen = []
    registry.changed.connect(lambda: seen.append(1))
    registry.poll()
    assert job.settled and seen == [1] and not registry._timer.isActive()
    registry.poll()
    assert seen == [1]  # an unchanged summary emits nothing


def test_poll_keeps_running_job_and_timer(registry):
    release = Event()
    worker = GatedWorker(release)
    job = registry.add(worker, "running")
    worker.start()
    try:
        assert worker.entered.wait(3)
        registry.poll()
        assert not job.settled and registry._timer.isActive()
    finally:
        release.set()
        assert worker.wait(5000)
    registry.poll()
    assert job.settled and job.state.snapshot().status == "succeeded"


def test_poll_deletes_only_owned_workers(registry):
    owned, kept = IdleWorker(), IdleWorker()
    for worker in (owned, kept):
        worker.job_state.finish()
    registry.add(owned, "owned", owned=True)
    registry.add(kept, "kept")
    registry.poll()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(owned) and isValid(kept)


def test_cancel_is_noop_once_settled(registry):
    worker = IdleWorker()
    worker.job_state.finish()
    job = registry.add(worker, "done")
    registry.poll()
    before = job.state.snapshot()
    seen = []
    registry.changed.connect(lambda: seen.append(1))
    registry.cancel(job)
    assert seen == [] and job.state.snapshot() == before and not job.state.cancelled


def test_cancel_unsettled_requests_cancellation_and_emits(registry):
    worker = IdleWorker()
    job = registry.add(worker, "pending")
    seen = []
    registry.changed.connect(lambda: seen.append(1))
    registry.cancel(job)
    assert seen == [1] and job.state.snapshot().status == "cancelling"


def test_retry_starts_failed_paths_once(registry, pump_until):
    calls = []

    def factory(paths):
        calls.append(paths)
        worker = IdleWorker(paths)
        worker.job_state.finish()
        return worker

    job = registry.add(_failed_worker(), "export", factory)
    registry.poll()
    following = registry.retry(job)
    try:
        assert calls == [("b",)] and job.retry_started
        assert following is registry.jobs[-1] and following.owned
        assert following.retry_factory is factory and following.title == "export"
        assert registry.retry(job) is None and calls == [("b",)]
    finally:
        assert following.worker.wait(5000)
    assert pump_until(lambda: (registry.poll(), following.settled)[1])


def test_retry_without_failures_or_factory_returns_none(registry):
    clean = IdleWorker()
    clean.job_state.record("a", output="ok")
    clean.job_state.finish()
    no_failures = registry.add(clean, "clean", lambda _p: pytest.fail("not retried"))
    no_factory = registry.add(_failed_worker(), "nofactory")
    registry.poll()
    assert registry.retry(no_failures) is None and registry.retry(no_factory) is None


def test_clear_finished_keeps_unsettled_and_emits(registry):
    done = IdleWorker()
    done.job_state.finish()
    registry.add(done, "done")
    registry.poll()
    live = registry.add(IdleWorker(), "live")
    seen = []
    registry.changed.connect(lambda: seen.append(1))
    registry.clear_finished()
    assert registry.jobs == [live] and seen == [1]


def test_job_registry_lives_on_application(qapp, monkeypatch):
    monkeypatch.setattr(qapp, "_imervue_jobs", None, raising=False)
    created = background_jobs.job_registry()
    try:
        assert qapp._imervue_jobs is created and created.parent() is qapp
        assert background_jobs.job_registry() is created
    finally:
        created.deleteLater()


def test_dialog_defaults_to_application_registry(qapp, registry, monkeypatch):
    monkeypatch.setattr(qapp, "_imervue_jobs", registry, raising=False)
    dialog = BackgroundJobsDialog(None)
    try:
        assert dialog._registry is registry
        assert dialog.windowTitle() == _word("background_jobs", "Background Jobs")
        assert dialog.tree.columnCount() == 3
        assert dialog.tree.headerItem().text(1) == _word("jobs_status", "Status")
    finally:
        dialog.deleteLater()


def test_rows_show_title_translated_status_and_progress(registry, panel):
    finishing = IdleWorker()
    finishing.job_state.record("a", output="ok")
    finishing.job_state.finish()
    registry.add(finishing, "first")
    registry.add(IdleWorker(("a", "b")), "second")
    rows = [panel.tree.topLevelItem(i) for i in range(panel.tree.topLevelItemCount())]
    assert [row.text(0) for row in rows] == ["first", "second"]
    assert rows[0].text(1) == _word("jobs_finishing", "finishing")
    assert rows[1].text(1) == _word("jobs_running", "running")
    assert [row.text(2) for row in rows] == ["1/1", "0/2"]
    assert all(row.childCount() == 0 for row in rows)
    registry.poll()
    assert panel.tree.topLevelItem(0).text(1) == _word("jobs_succeeded", "succeeded")


def test_selected_job_details_and_button_states(registry, panel):
    factory_calls = []
    job = registry.add(_failed_worker(), "export", factory_calls.append)
    assert panel.cancel_button.isEnabled() is False  # nothing selected
    panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
    assert panel.cancel_button.isEnabled() and not panel.retry_button.isEnabled()
    registry.poll()
    root = panel.tree.topLevelItem(0)
    assert panel.tree.currentItem() is root and root.isExpanded()
    assert not panel.cancel_button.isEnabled() and panel.retry_button.isEnabled()
    children = [root.child(i) for i in range(root.childCount())]
    assert [c.text(0) for c in children] == ["b", "a"]  # failures first
    assert children[0].text(1) == _word("jobs_failed", "failed")
    assert children[0].text(2) == "broken" and children[1].text(2) == "out-a.png"
    assert children[0].data(1, Qt.ItemDataRole.UserRole) == ""
    assert children[1].data(1, Qt.ItemDataRole.UserRole) == "out-a.png"
    assert [children[1].toolTip(i) for i in range(3)] == [
        children[1].text(i) for i in range(3)
    ]
    panel.tree.setCurrentItem(children[0])
    assert panel._selected() is job and panel.retry_button.isEnabled()
    job.retry_started = True
    panel._buttons()
    assert not panel.retry_button.isEnabled()


def test_more_row_appears_past_visible_limit(registry, panel):
    worker = IdleWorker([str(i) for i in range(501)])
    for i in range(501):
        worker.job_state.record(str(i), output=f"o{i}")
    worker.job_state.finish()
    registry.add(worker, "large")
    registry.poll()
    panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
    root = panel.tree.topLevelItem(0)
    assert root.childCount() == 501
    more = root.child(500)
    assert more.text(0) == _word("jobs_more", "More results are available in the full report")
    assert (more.text(1), more.text(2)) == ("", "")


def test_open_output_ignores_rows_without_output(registry, panel, monkeypatch):
    opened = []
    monkeypatch.setattr(background_jobs.QDesktopServices, "openUrl", opened.append)
    registry.add(_failed_worker(), "export")
    registry.poll()
    panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
    root = panel.tree.topLevelItem(0)
    panel._open_output(root.child(0), 0)
    assert opened == []
    panel._open_output(root.child(1), 0)
    assert [url.toLocalFile() for url in opened] == ["out-a.png"]


def test_panel_cancel_and_retry_route_to_registry(registry, panel, monkeypatch):
    calls = []
    monkeypatch.setattr(registry, "cancel", lambda job: calls.append(("cancel", job)))
    monkeypatch.setattr(registry, "retry", lambda job: calls.append(("retry", job)))
    job = registry.add(IdleWorker(), "x")
    panel._cancel()
    panel._retry()
    assert calls == []
    panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
    panel._cancel()
    panel._retry()
    assert calls == [("cancel", job), ("retry", job)]


def test_open_background_jobs_reuses_one_panel_per_window(qapp, monkeypatch):
    from types import SimpleNamespace

    from PySide6.QtCore import QObject

    calls = []

    class FakePanel(QObject):
        def __init__(self, parent):
            super().__init__()
            calls.append(("new", parent))

        def show(self):
            calls.append("show")

        def raise_(self):
            calls.append("raise")

        def activateWindow(self):  # noqa: N802 - Qt method name
            calls.append("activate")

    monkeypatch.setattr(background_jobs, "BackgroundJobsDialog", FakePanel)
    ui = SimpleNamespace()
    open_background_jobs(ui)
    first = ui._background_jobs_dialog
    open_background_jobs(ui)
    assert ui._background_jobs_dialog is first
    assert calls == [("new", ui), "show", "raise", "activate", "show", "raise", "activate"]
    first.deleteLater()
