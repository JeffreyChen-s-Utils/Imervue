"""Actual QThreads outlive dialogs; only failed sources are retried once."""

from functools import partial
from pathlib import Path
from threading import Event

import pytest
from PIL import Image
from PySide6.QtCore import QThread, Qt

from Imervue.gui.background_jobs import BackgroundJobsDialog, JobRegistry, job_registry
from Imervue.gui.batch_export_dialog import ExportSettings, _ExportWorker
from Imervue.system.job_state import JobState


class BlockedWorker(QThread):
    def __init__(self, release):
        super().__init__()
        self.release = release
        self.entered = Event()
        self.job_state = JobState(["source"])

    def run(self):
        self.entered.set()
        self.release.wait(5)
        if self.job_state.cancelled:
            self.job_state.finish()
        else:
            self.job_state.record("source", output="result")
            self.job_state.finish()


@pytest.fixture
def registry(qapp):
    value = JobRegistry()
    yield value
    value.drain()
    value.poll()
    value.deleteLater()


def test_cancel_keeps_uninterruptible_worker_and_results_after_panel_close(registry, pump_until):
    release = Event()
    worker = BlockedWorker(release)
    job = registry.add(worker, "blocked")
    panel = BackgroundJobsDialog(registry=registry)
    worker.start()
    try:
        assert worker.entered.wait(3)
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
        panel.cancel_button.click()
        panel.close()
        registry.clear_finished()
        assert registry.jobs == [job] and not job.settled
        assert worker.isRunning() and job.state.snapshot().status == "cancelling"
        release.set()
        assert pump_until(lambda: job.settled)
        assert job.state.snapshot().status == "cancelled"
        assert job.state.failed_paths() == ()
        registry.clear_finished()
        assert registry.jobs == []
    finally:
        release.set()
        assert worker.wait(5000)
        panel.deleteLater()


def test_real_export_retry_does_not_touch_completed_output(
    registry,
    qapp,
    pump_until,
    tmp_path,
    monkeypatch,
):
    from Imervue.gui import batch_export_dialog as module

    sources = [str(tmp_path / name) for name in ("one.png", "two.png")]
    out = tmp_path / "outputs"
    out.mkdir()
    for source in sources:
        Image.new("RGB", (4, 3), (10, 20, 30)).save(source)
    original = module.open_export_source
    attempted = []
    failed = True

    def decode(path, renderer):
        attempted.append(path)
        if failed and path == sources[1]:
            raise OSError("disk full")
        return original(path, renderer)

    monkeypatch.setattr(module, "open_export_source", decode)
    settings = ExportSettings("PNG", 90)
    worker = _ExportWorker(sources, str(out), settings)
    job = registry.add(
        worker, "Export", partial(_ExportWorker, output_dir=str(out), settings=settings)
    )
    worker.start()
    panel = BackgroundJobsDialog(registry=registry)
    try:
        assert pump_until(lambda: job.settled)
        assert job.state.snapshot().status == "partial"
        saved = out / "one.png"
        prior = saved.read_bytes()
        failed = False
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
        panel.refresh()
        root = panel.tree.topLevelItem(0)
        assert root.childCount() == 2  # selection/refresh must not duplicate rows
        assert root.child(0).text(2) == "disk full"
        assert root.child(0).toolTip(0) == sources[1]
        opened = []
        monkeypatch.setattr(module, "open_export_source", decode)
        from Imervue.gui import background_jobs

        monkeypatch.setattr(background_jobs.QDesktopServices, "openUrl", opened.append)
        panel._open_output(root.child(1), 0)
        assert Path(opened[0].toLocalFile()) == saved
        panel.retry_button.click()
        following = registry.jobs[-1]
        assert following is not job and registry.retry(job) is None
        assert pump_until(lambda: following.settled)
        assert following.state.snapshot().status == "succeeded"
        assert attempted == [*sources, sources[1]]
        assert saved.read_bytes() == prior and sorted(p.name for p in out.iterdir()) == [
            "one.png",
            "two.png",
        ]
    finally:
        assert worker.wait(5000)
        registry.drain()
        panel.deleteLater()


def test_registry_shared_by_windows_and_retry_factory_failure(registry, qapp, caplog):
    assert job_registry() is job_registry()
    worker = BlockedWorker(Event())
    worker.job_state.finish(error="offline")

    def broken(_paths):
        raise OSError("missing model")

    job = registry.add(worker, "failure", broken)
    assert registry.retry(job) is None  # not yet settled
    registry.poll()
    assert job.settled
    with caplog.at_level("ERROR"):
        assert registry.retry(job) is None
    assert not job.retry_started and "missing model" in caplog.text
    panel = BackgroundJobsDialog(registry=registry)
    try:
        panel.tree.setCurrentItem(None)
        assert not panel.cancel_button.isEnabled() and not panel.retry_button.isEnabled()
        panel._open_output(panel.tree.topLevelItem(0), 0)
        panel._cancel()
        panel._retry()
        assert panel.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) is job
    finally:
        panel.deleteLater()


def test_parent_deletion_cannot_destroy_registered_running_thread(registry, qapp, pump_until):
    from PySide6.QtWidgets import QDialog
    from shiboken6 import isValid, delete

    release = Event()
    owner = QDialog()
    worker = BlockedWorker(release)
    worker.setParent(owner)
    job = registry.add(worker, "retained")
    assert worker.parent() is None
    worker.start()
    try:
        assert worker.entered.wait(3)
        delete(owner)
        assert not isValid(owner)
        assert isValid(worker) and worker.isRunning() and not job.settled
        release.set()
        assert pump_until(lambda: job.settled)
        assert job.state.snapshot().items[0].output == "result"
    finally:
        release.set()
        assert worker.wait(5000)


def test_panel_bounds_rows_but_report_contains_all_results(
    registry,
    qapp,
    tmp_path,
    monkeypatch,
    caplog,
):
    import json
    from Imervue.gui import background_jobs as module

    worker = BlockedWorker(Event())
    worker.job_state = JobState([str(i) for i in range(510)])
    for i in range(510):
        worker.job_state.record(str(i), output=f"result-{i}")
    worker.job_state.finish()
    job = registry.add(worker, "large")
    registry.poll()
    panel = BackgroundJobsDialog(registry=registry)
    target = tmp_path / "report.json"
    try:
        panel._save_report()  # no selected task
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
        assert panel.tree.topLevelItem(0).childCount() == 501
        monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *_: (str(target), "JSON"))
        panel._save_report()
        report = json.loads(target.read_text(encoding="utf-8"))
        assert report["title"] == job.title and len(report["items"]) == 510
        assert report["items"][-1]["output"] == "result-509"
        prior = target.read_bytes()
        monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *_: ("", ""))
        panel._save_report()
        assert target.read_bytes() == prior
        monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *_: (str(target), ""))

        def broken(*_args):
            raise OSError("permission")

        monkeypatch.setattr(module, "write_text_atomically", broken)
        warned = []
        monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: warned.append(args[-1]))
        with caplog.at_level("ERROR"):
            panel._save_report()
        assert warned == ["permission"] and "permission" in caplog.text
        assert target.read_bytes() == prior
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("invalid", [None, "missing_state"])
def test_invalid_retry_factory_keeps_original_failure_available(registry, invalid, caplog):
    worker = BlockedWorker(Event())
    worker.job_state.finish(error="failed")
    job = registry.add(worker, "invalid",
                       lambda _paths: QThread() if invalid == "missing_state" else invalid)
    registry.poll()
    with caplog.at_level("ERROR"):
        assert registry.retry(job) is None
    assert registry.jobs == [job] and not job.retry_started
    assert "requires a QThread" in caplog.text


def test_explicit_exit_drain_joins_actual_work_and_does_not_create_registry(
    registry,
    qapp,
    monkeypatch,
):
    from threading import Timer
    from Imervue.gui.background_jobs import drain_background_jobs

    monkeypatch.setattr(qapp, "_imervue_jobs", None, raising=False)
    drain_background_jobs()
    assert qapp._imervue_jobs is None
    monkeypatch.setattr(qapp, "_imervue_jobs", registry)
    release = Event()
    worker = BlockedWorker(release)
    registry.add(worker, "exit")
    worker.start()
    timer = Timer(0.1, release.set)
    try:
        assert worker.entered.wait(3)
        timer.start()
        drain_background_jobs()
        assert not worker.isRunning() and worker.wait(0)
        assert worker.job_state.snapshot().status == "cancelled"
    finally:
        release.set()
        assert worker.wait(5000)
        timer.join(3)


def test_completed_inline_job_is_retained_and_validation_is_explicit(registry):
    state = JobState(["a"])
    with pytest.raises(ValueError):
        registry.add_completed("Export", state)
    state.record("a", output="result.png")
    state.finish()
    job = registry.add_completed("Export", state)
    assert job.settled and registry.jobs[-1] is job
    assert job.state.snapshot().items[0].output == "result.png"
    registry.clear_finished()
    assert not registry.jobs
