"""Tests for the webcam preview dialog + tracker snapshot.

Real camera + mediapipe aren't available in CI — the tracker's
``_tracking_loop`` is ``pragma: no cover`` for that reason. These
tests cover the pure-Python pieces:

1. ``WebcamTracker.current_preview_state`` returns a defensive
   snapshot (no shared mutable references) with the expected keys.
2. ``_frame_to_pixmap`` converts a fake BGR frame + landmarks into a
   non-empty QPixmap, mirroring the frame horizontally so the
   "selfie view" feels right.
3. The dialog instantiates under qapp and renders its initial
   "waiting for first frame" state without crashing.
"""
from __future__ import annotations
import numpy as np
import pytest


# QOpenGLWidget construction segfaults on the headless GitHub
# Actions Windows runner once the offscreen-GL pool is exhausted
# (see tests/conftest.py::skip_on_headless_ci). All tests in this
# file touch a real PuppetCanvas / PuppetWorkspace, so the whole
# module skips on CI; local runs cover them.
import os as _os_for_skip  # noqa: E402
import pytest as _pytest_for_skip  # noqa: E402

pytestmark = _pytest_for_skip.mark.skipif(
    _os_for_skip.environ.get("CI") == "true"
    or _os_for_skip.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QOpenGLWidget construction segfaults on headless CI runner",
)



def test_tracker_preview_snapshot_keys_match_contract(qapp):
    """``current_preview_state`` is the contract between the tracker
    and the preview dialog — every key the dialog reads must exist
    on the returned dict, with sensible defaults before the first
    frame lands."""
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.webcam_tracker import WebcamTracker
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    try:
        state = tracker.current_preview_state()
        assert set(state) == {
            "frame_bgr", "landmarks_norm", "face_detected",
            "fps", "camera_open", "error",
        }
        assert state["frame_bgr"] is None
        assert state["landmarks_norm"] is None
        assert state["face_detected"] is False
        assert state["fps"] == pytest.approx(0.0)
        assert state["camera_open"] is False
        assert state["error"] is None
    finally:
        canvas.deleteLater()


def test_tracker_preview_snapshot_returns_independent_copy(qapp):
    """Mutating the returned snapshot must not affect the tracker's
    internal arrays — otherwise the GUI thread could race the
    capture thread through a shared reference."""
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.webcam_tracker import WebcamTracker
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    try:
        # Inject a fake frame the way the capture thread would.
        with tracker._preview_lock:   # noqa: SLF001
            tracker._latest_frame_bgr = np.zeros((4, 4, 3), dtype=np.uint8)   # noqa: SLF001
            tracker._latest_landmarks_norm = np.zeros((10, 3), dtype=np.float64)   # noqa: SLF001
            tracker._face_detected = True   # noqa: SLF001
        snap = tracker.current_preview_state()
        snap["frame_bgr"][0, 0] = [255, 255, 255]   # caller-side mutation
        # Internal array must remain untouched.
        with tracker._preview_lock:   # noqa: SLF001
            assert tracker._latest_frame_bgr[0, 0].tolist() == [0, 0, 0]   # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_frame_to_pixmap_mirrors_and_preserves_size(qapp):
    """The preview should show a mirrored ("selfie view") image at
    the original frame size so the user sees themselves the right
    way around. The pixmap's dimensions must match the input BGR
    frame."""
    from Imervue.puppet.webcam_preview_dialog import _frame_to_pixmap
    frame = np.zeros((60, 80, 3), dtype=np.uint8)
    # Set a single bright-red pixel at column 0 — after horizontal
    # mirroring it should land at column W-1.
    frame[:, 0] = [0, 0, 255]   # BGR red
    pixmap = _frame_to_pixmap(frame, None)
    assert not pixmap.isNull()
    assert pixmap.width() == 80
    assert pixmap.height() == 60
    image = pixmap.toImage()
    # Right-most column carries the red marker post-mirror.
    last_col_pixel = image.pixelColor(79, 30)
    assert last_col_pixel.red() > 200
    assert last_col_pixel.blue() < 50


def test_frame_to_pixmap_rejects_wrong_shape(qapp):
    """Helper validates input shape so the dialog can't accidentally
    paint garbage into a label."""
    from Imervue.puppet.webcam_preview_dialog import _frame_to_pixmap
    with pytest.raises(ValueError):
        _frame_to_pixmap(np.zeros((10, 10), dtype=np.uint8), None)
    with pytest.raises(ValueError):
        _frame_to_pixmap(np.zeros((10, 10, 4), dtype=np.uint8), None)


def test_dialog_constructs_and_shows_waiting_state(qapp):
    """Construct the dialog with a tracker that's never seen a frame.
    The status text should announce we're waiting for the camera
    rather than crashing or showing a blank label."""
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.webcam_preview_dialog import WebcamPreviewDialog
    from Imervue.puppet.webcam_tracker import WebcamTracker
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    dlg = WebcamPreviewDialog(tracker)
    try:
        # Pre-show state: the seed _refresh() in __init__ should have
        # populated a status line.
        status_text = dlg._status_label.text()   # noqa: SLF001
        assert status_text  # not empty
    finally:
        dlg.deleteLater()
        canvas.deleteLater()


def test_dialog_close_disables_tracker(qapp):
    """Closing the preview dialog must stop the tracker — otherwise
    the camera light stays on with no UI to surface it."""
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.webcam_preview_dialog import WebcamPreviewDialog
    from Imervue.puppet.webcam_tracker import WebcamTracker
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    dlg = WebcamPreviewDialog(tracker)
    try:
        # Pretend the tracker is enabled.
        tracker._enabled = True   # noqa: SLF001
        dlg.close()
        assert tracker.is_enabled() is False
    finally:
        dlg.deleteLater()
        canvas.deleteLater()
