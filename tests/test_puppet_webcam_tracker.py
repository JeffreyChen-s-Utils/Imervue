"""Smoke tests for WebcamTracker — the actual mediapipe / OpenCV
pipeline isn't reachable in CI (no camera, optional deps), so we only
exercise the API contract: construction, toggle, graceful degrade
when imports fail.
"""
from __future__ import annotations
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.webcam_tracker import WebcamTracker

from _qt_skip import pytestmark  # noqa: E402,F401


def test_tracker_starts_disabled(qapp):
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    try:
        assert tracker.is_enabled() is False
    finally:
        tracker.deleteLater()
        canvas.deleteLater()


def test_tracker_set_enabled_returns_status(qapp):
    """Whether mediapipe is installed or not, ``set_enabled(True)``
    must return a bool — never raise. CI typically lacks the deps,
    expect False; dev machines with mediapipe + a camera return True
    and stop cleanly."""
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    try:
        result = tracker.set_enabled(True)
        assert isinstance(result, bool)
        tracker.set_enabled(False)
    finally:
        tracker.shutdown()
        tracker.deleteLater()
        canvas.deleteLater()


def test_tracker_repeated_disable_is_idempotent(qapp):
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    try:
        tracker.set_enabled(False)
        tracker.set_enabled(False)
    finally:
        tracker.deleteLater()
        canvas.deleteLater()


def test_tracker_shutdown_safe_when_idle(qapp):
    canvas = PuppetCanvas()
    tracker = WebcamTracker(canvas)
    try:
        tracker.shutdown()
    finally:
        tracker.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Tasks API migration helpers
# ---------------------------------------------------------------------------


def test_https_urlopen_rejects_non_https_scheme():
    """The HTTPS guard must refuse http:// / file:// / ftp:// URLs
    so a future maintainer can't accidentally fetch the model over
    an insecure channel. Mirrors the pip_installer / plugin_downloader
    convention."""
    import pytest
    from Imervue.puppet.webcam_tracker import _https_urlopen, _WebcamSetupError
    for bad in (
        "http://example.com/face_landmarker.task",   # NOSONAR - negative test
        "file:///etc/passwd",
        "ftp://example.com/asset.task",   # NOSONAR - negative test
    ):
        with pytest.raises(_WebcamSetupError):
            _https_urlopen(bad)


def test_landmarks_to_array_handles_tasks_api_shape():
    """The Tasks API returns a list of NormalizedLandmark objects
    with ``.x / .y / .z``. Our helper must turn that into the same
    (N, 3) float64 array the legacy code produced — so the rest of
    the pipeline (face_landmark_mapper, params) doesn't need to
    change."""
    import numpy as np
    import pytest
    from types import SimpleNamespace
    from Imervue.puppet.webcam_tracker import _landmarks_to_array

    fake_landmarks = [
        SimpleNamespace(x=0.1, y=0.2, z=0.0),
        SimpleNamespace(x=0.5, y=0.5, z=-0.1),
        SimpleNamespace(x=0.9, y=0.8, z=0.05),
    ]
    arr = _landmarks_to_array(fake_landmarks)
    assert arr.shape == (3, 3)
    assert arr.dtype == np.float64
    assert arr[1, 0] == pytest.approx(0.5)
    assert arr[2, 2] == pytest.approx(0.05)
