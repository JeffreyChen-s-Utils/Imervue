"""Observable camera lifecycle, recovery controls, and durable output history."""

import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtGui import QAction
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from Imervue.gui.background_jobs import BackgroundJobsDialog, JobRegistry
from Imervue.gui.job_indicator import JobIndicator, install_job_indicator
from Imervue.puppet import webcam_tracker as webcam
from Imervue.puppet.webcam_preview_dialog import WebcamPreviewDialog
from Imervue.puppet.webcam_status import WebcamPhase
from Imervue.puppet.workspace_live import PuppetLiveMixin
from Imervue.puppet.recorder import RecordingSession
from Imervue.system.job_state import JobState


@pytest.fixture
def tracker(qapp):
    value = webcam.WebcamTracker(SimpleNamespace(document=lambda: None))
    yield value
    value.shutdown()
    if value._thread is not None:
        value._thread.join(3)
        assert not value._thread.is_alive()
    value.deleteLater()


def backend(monkeypatch, capture):
    detector = SimpleNamespace(close=lambda: None)
    monkeypatch.setitem(sys.modules, "mediapipe", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(
        VideoCapture=capture, COLOR_BGR2RGB=1, cvtColor=lambda frame, _: frame,
    ))
    monkeypatch.setattr(webcam, "_build_face_landmarker", lambda: detector)
    monkeypatch.setattr(webcam, "_detect_face", lambda *_: None)
    return detector


def test_missing_dependency_has_specific_recovery(tracker, monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", None)
    assert not tracker.set_enabled(True)
    assert tracker.status().phase == WebcamPhase.MISSING_DEPENDENCY
    assert not tracker.is_enabled()
    panel = WebcamPreviewDialog(tracker)
    try:
        assert not panel._install_button.isHidden()
        assert panel._retry_button.isEnabled()
        assert panel._diagnostics.text()
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("phase,error", [
    (WebcamPhase.PERMISSION_DENIED, PermissionError("camera permission denied")),
    (WebcamPhase.FAILED, RuntimeError("driver initialization failed")),
])
def test_driver_errors_keep_actual_reason(tracker, monkeypatch, pump_until, phase, error):
    def open_camera(_index):
        raise error

    backend(monkeypatch, open_camera)
    tracker.set_enabled(True)
    assert pump_until(lambda: tracker.can_configure())
    assert tracker.status().phase == phase
    assert tracker.status().detail == str(error)
    assert not tracker.is_enabled()


def test_unavailable_camera_releases_resources_and_accepts_new_device(
    tracker, monkeypatch, pump_until,
):
    released, devices = [], []

    def open_camera(index):
        devices.append(index)
        return SimpleNamespace(isOpened=lambda: False, release=lambda: released.append("camera"))

    detector = backend(monkeypatch, open_camera)
    detector.close = lambda: released.append("detector")
    assert tracker.set_device(2)
    tracker.set_enabled(True)
    assert pump_until(lambda: tracker.can_configure())
    assert tracker.status().phase == WebcamPhase.DEVICE_UNAVAILABLE
    assert devices == [2] and released == ["camera", "detector"]
    panel = WebcamPreviewDialog(tracker)
    try:
        assert panel._install_button.isHidden()
        assert panel._device.isEnabled()
        panel._device.setValue(4)
        panel._retry_button.click()
        assert pump_until(lambda: tracker.can_configure())
        assert devices == [2, 4]
    finally:
        panel.deleteLater()


def test_model_file_permission_error_does_not_claim_camera_permission_denied(
    tracker, monkeypatch, pump_until,
):
    backend(monkeypatch, lambda _index: None)

    def build():
        raise PermissionError("cannot write model cache")

    monkeypatch.setattr(webcam, "_build_face_landmarker", build)
    tracker.set_enabled(True)
    assert pump_until(lambda: tracker.can_configure())
    assert tracker.status().phase == WebcamPhase.FAILED
    assert tracker.status().detail == "cannot write model cache"


def test_stop_never_waits_for_capture_and_toggle_tracks_worker(tracker, monkeypatch, pump_until):
    entered, release = Event(), Event()
    calls = []

    def read():
        calls.append("read")
        if len(calls) == 1:
            return True, np.zeros((4, 4, 3), np.uint8)
        entered.set()
        release.wait(4)
        return False, None

    backend(monkeypatch, lambda _: SimpleNamespace(
        isOpened=lambda: True, read=read, release=lambda: calls.append("released"),
    ))
    toggle = QAction()
    toggle.setCheckable(True)
    owner = SimpleNamespace(_webcam=tracker, _webcam_toggle=toggle)
    tracker.state_changed.connect(lambda: PuppetLiveMixin._on_webcam_state_changed(owner))
    try:
        assert tracker.set_enabled(True)
        assert pump_until(lambda: tracker.status().phase == WebcamPhase.RUNNING)
        assert entered.wait(2)
        tracker._pump_to_canvas()
        assert toggle.isChecked()
        tracker.set_enabled(False)
        assert not release.is_set() and tracker._thread.is_alive()
        assert tracker.status().phase == WebcamPhase.STOPPING
        assert not toggle.isChecked() and not toggle.isEnabled()
        assert not tracker.set_enabled(True)
        assert not tracker.set_device(3)
        release.set()
        assert pump_until(lambda: tracker.status().phase == WebcamPhase.STOPPED)
        assert toggle.isEnabled() and calls[-1] == "released"
    finally:
        release.set()


def test_indicator_keeps_failure_count_and_opens_existing_panel(qapp, monkeypatch):
    window = QMainWindow()
    registry = JobRegistry()
    state = JobState(["capture.png"])
    state.finish(error="disk full")
    indicator = JobIndicator(window, registry=registry)
    registry.add_completed("Capture", state)
    assert "1" in indicator.text() and "failed" in indicator.text()
    opened = []
    monkeypatch.setattr("Imervue.gui.job_indicator.open_background_jobs", opened.append)
    indicator.click()
    assert opened == [window]
    assert install_job_indicator(window).parent() == window.statusBar()
    registry.clear_finished()
    assert "1" not in indicator.text()
    window.deleteLater()
    registry.deleteLater()


def test_deleted_tracker_never_calls_qt_from_blocked_capture(qapp, monkeypatch):
    from shiboken6 import delete

    entered, release = Event(), Event()

    def read():
        entered.set()
        release.wait(3)
        return False, None

    backend(monkeypatch, lambda _: SimpleNamespace(
        isOpened=lambda: True, read=read, release=lambda: None,
    ))
    tracker = webcam.WebcamTracker(SimpleNamespace(document=lambda: None))
    try:
        tracker.set_enabled(True)
        assert entered.wait(2)
        worker = tracker._thread
        tracker.shutdown()
        delete(tracker)
        release.set()
        worker.join(2)
        assert not worker.is_alive()
    finally:
        release.set()


def test_escape_stops_tracking_even_when_dialog_is_rejected(tracker, qapp):
    tracker._enabled = True
    tracker._set_status(WebcamPhase.RUNNING)
    dialog = WebcamPreviewDialog(tracker)
    dialog.show()
    qapp.processEvents()
    try:
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        assert not tracker.is_enabled()
        assert tracker.status().phase == WebcamPhase.STOPPED
        assert not dialog.isVisible()
    finally:
        dialog.deleteLater()


def test_history_retains_destination_and_only_success_is_openable(qapp, monkeypatch, tmp_path):
    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    good, bad = tmp_path / "one" / "clip.gif", tmp_path / "two" / "clip.gif"
    PuppetLiveMixin._retain_output_result("record", "Record", str(good))
    PuppetLiveMixin._retain_output_result("record", "Record", str(bad), "disk full")
    panel = BackgroundJobsDialog(registry=registry)
    opened = []
    monkeypatch.setattr("Imervue.gui.background_jobs.QDesktopServices.openUrl", opened.append)
    try:
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0).child(0))
        assert panel.open_button.isEnabled() and panel.folder_button.isEnabled()
        panel.refresh()
        assert panel.tree.currentItem().parent() is not None
        panel.open_button.click()
        panel.folder_button.click()
        assert [Path(url.toLocalFile()) for url in opened] == [good, good.parent]
        panel.tree.setCurrentItem(panel.tree.topLevelItem(1))
        panel.tree.setCurrentItem(panel.tree.topLevelItem(1).child(0))
        assert not panel.open_button.isEnabled() and not panel.folder_button.isEnabled()
        assert not panel.retry_button.isEnabled()
        failure = registry.jobs[1].state.snapshot().items[0]
        assert failure.source == str(bad) and failure.error == "disk full"
    finally:
        panel.deleteLater()
        registry.deleteLater()


class LiveWindow(PuppetLiveMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self._canvas = SimpleNamespace(
            document=lambda: SimpleNamespace(size=(16, 16)),
            render_offscreen_puppet=lambda *_args, **_kwargs: self.frame(),
        )
        self._record_action = QAction(self)
        self._record_action.setCheckable(True)
        self._recorder = RecordingSession(self._canvas, self)
        self._recorder.finished.connect(self._on_recording_finished)
        self._recorder.failed.connect(self._on_recording_failed)
        self.messages = []

    @staticmethod
    def frame():
        image = QImage(16, 16, QImage.Format.Format_RGB888)
        image.fill(0xffdd44)
        return image

    def _announce(self, key, fallback, **values):
        self.messages.append(fallback.format(**values))


def test_recording_is_counted_until_finalized_and_retains_real_clip(qapp, monkeypatch, tmp_path):
    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    destination = tmp_path / "clip.gif"
    monkeypatch.setattr("Imervue.puppet.workspace_live.QFileDialog.getSaveFileName",
                        lambda *_args: (str(destination), ""))
    window = LiveWindow()
    indicator = JobIndicator(window, registry=registry)
    try:
        window._start_recording()
        job = registry.jobs[0]
        assert not job.settled and "1 running" in indicator.text()
        window._recorder._on_tick()
        registry.cancel(job)
        assert job.settled and destination.is_file()
        assert job.state.snapshot().items[0].output == str(destination)
        assert job.retry_factory is None and registry.retry(job) is None
        assert str(destination) in window.messages[-1]
        assert "0 running" in indicator.text()
    finally:
        window._recorder.stop()
        window.deleteLater()
        registry.deleteLater()


def test_capture_history_preserves_actual_write_failure(qapp, monkeypatch, tmp_path):
    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    destination = blocker / "frame.png"
    monkeypatch.setattr("Imervue.puppet.workspace_live.QFileDialog.getSaveFileName",
                        lambda *_args: (str(destination), ""))
    window = LiveWindow()
    try:
        window._capture_via_dialog()
        result = registry.jobs[0].state.snapshot().items[0]
        assert result.status == "failed" and result.error and not result.output
        assert result.source == str(destination)
        assert blocker.name in result.error
        destination = tmp_path / "frame.png"
        window._capture_via_dialog()
        result = registry.jobs[1].state.snapshot().items[0]
        assert result.output == str(destination) and destination.is_file()
    finally:
        window.deleteLater()
        registry.deleteLater()


def test_stopping_a_recording_reports_finalization_failure(qapp, monkeypatch, tmp_path):
    import imageio

    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    destination = tmp_path / "clip.gif"
    monkeypatch.setattr("Imervue.puppet.workspace_live.QFileDialog.getSaveFileName",
                        lambda *_args: (str(destination), ""))

    def close():
        raise OSError("disk full during finalization")

    monkeypatch.setattr(imageio, "get_writer", lambda *_args, **_kwargs:
                        SimpleNamespace(close=close))
    window = LiveWindow()
    indicator = JobIndicator(window, registry=registry)
    try:
        window._start_recording()
        job = registry.jobs[0]
        registry.cancel(job)
        snapshot = job.state.snapshot()
        assert snapshot.status == "failed"
        assert snapshot.items[0].source == str(destination)
        assert snapshot.items[0].error == "disk full during finalization"
        assert not snapshot.items[0].output
        assert "1 failed" in indicator.text()
    finally:
        window.deleteLater()
        registry.deleteLater()


@pytest.mark.parametrize("extension", [".gif", ".mp4"])
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("unready_ticks", [0, 3])
def test_empty_real_recording_never_publishes_output(
    qapp, monkeypatch, tmp_path, extension, existing, unready_ticks,
):
    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    destination = tmp_path / f"clip{extension}"
    original = b"previous user recording"
    if existing:
        destination.write_bytes(original)
    monkeypatch.setattr("Imervue.puppet.workspace_live.QFileDialog.getSaveFileName",
                        lambda *_args: (str(destination), ""))
    window = LiveWindow()
    window._canvas.render_offscreen_puppet = lambda *_args, **_kwargs: QImage()
    successes = []
    window._recorder.finished.connect(successes.append)
    try:
        window._start_recording()
        assert window._recorder.is_recording()
        for _ in range(unready_ticks):
            window._recorder._on_tick()
        assert window._recorder.stop() is None
        assert not successes
        item = registry.jobs[0].state.snapshot().items[0]
        assert item.status == "failed" and not item.output
        assert "No frames were captured" in item.error
        if existing:
            assert destination.read_bytes() == original
        else:
            assert not destination.exists()
        assert not list(tmp_path.glob(".imervue-record-*"))
    finally:
        window._recorder.stop()
        window.deleteLater()
        registry.deleteLater()


@pytest.mark.parametrize("missing_file", [False, True])
def test_encoder_must_create_nonempty_output_before_success(
    qapp, monkeypatch, tmp_path, missing_file,
):
    import imageio

    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    destination = tmp_path / "clip.gif"
    destination.write_bytes(b"existing recording")

    def writer(path, **_kwargs):
        def close():
            if missing_file:
                Path(path).unlink()
        return SimpleNamespace(append_data=lambda _frame: None, close=close)

    monkeypatch.setattr(imageio, "get_writer", writer)
    window = LiveWindow()
    failures, successes = [], []
    window._recorder.failed.connect(failures.append)
    window._recorder.finished.connect(successes.append)
    try:
        assert window._recorder.start(destination)
        window._recorder._on_tick()
        assert window._recorder.stop() is None
        assert failures and not successes
        assert destination.read_bytes() == b"existing recording"
        assert not list(tmp_path.glob(".imervue-record-*"))
    finally:
        window.deleteLater()
        registry.deleteLater()


@pytest.mark.parametrize("failure", ["append", "close", "replace"])
def test_recording_write_failures_preserve_prior_destination(
    qapp, monkeypatch, tmp_path, failure,
):
    import imageio
    from Imervue.puppet import recorder

    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    destination = tmp_path / "clip.gif"
    destination.write_bytes(b"existing recording")

    def fail(*_args):
        raise OSError(f"{failure} failed")

    def writer(path, **_kwargs):
        return SimpleNamespace(
            append_data=fail if failure == "append" else lambda _frame: Path(path).write_bytes(b"GIF"),
            close=fail if failure == "close" else lambda: None,
        )

    monkeypatch.setattr(imageio, "get_writer", writer)
    if failure == "replace":
        monkeypatch.setattr(recorder.os, "replace", fail)
    window = LiveWindow()
    failures, successes = [], []
    window._recorder.failed.connect(failures.append)
    window._recorder.finished.connect(successes.append)
    try:
        assert window._recorder.start(destination)
        window._recorder._on_tick()
        assert window._recorder.stop() is None
        assert failures == [f"{failure} failed"] and not successes
        assert destination.read_bytes() == b"existing recording"
        assert not list(tmp_path.glob(".imervue-record-*"))
    finally:
        window.deleteLater()
        registry.deleteLater()


def test_successful_recording_replaces_original_only_after_finalization(
    qapp, monkeypatch, tmp_path,
):
    from PIL import Image

    registry = JobRegistry()
    monkeypatch.setattr("Imervue.puppet.workspace_live.job_registry", lambda: registry)
    destination = tmp_path / "clip.gif"
    destination.write_bytes(b"existing recording")
    monkeypatch.setattr("Imervue.puppet.workspace_live.QFileDialog.getSaveFileName",
                        lambda *_args: (str(destination), ""))
    window = LiveWindow()
    successes = []
    window._recorder.finished.connect(successes.append)
    try:
        window._start_recording()
        window._recorder._on_tick()
        assert destination.read_bytes() == b"existing recording"
        assert window._recorder.stop() == str(destination)
        assert successes == [str(destination)]
        with Image.open(destination) as image:
            assert image.size == (16, 16)
        assert not list(tmp_path.glob(".imervue-record-*"))
    finally:
        window._recorder.stop()
        window.deleteLater()
        registry.deleteLater()
