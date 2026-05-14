"""Smoke tests for WebcamTracker — the actual mediapipe / OpenCV
pipeline isn't reachable in CI (no camera, optional deps), so we only
exercise the API contract: construction, toggle, graceful degrade
when imports fail.
"""
from __future__ import annotations

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.webcam_tracker import WebcamTracker


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


def test_face_landmarker_model_path_reuses_cached_file(tmp_path, monkeypatch):
    """When the model already exists on disk the path helper must
    return it without re-hitting the network."""
    from Imervue.puppet import webcam_tracker as wt

    monkeypatch.setattr(
        "Imervue.system.app_paths.app_dir",
        lambda: tmp_path,
    )
    cached = tmp_path / "models" / "face_landmarker.task"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"fake-model-bytes")

    # If we accidentally hit the network the test would actually
    # try to fetch from GCS, slowing CI to a crawl. Asserting that
    # the network call isn't made is enough.
    call_count = {"n": 0}
    def _no_network(_url):   # noqa: ANN001
        call_count["n"] += 1
        raise AssertionError("should not have called the network")
    monkeypatch.setattr(wt, "_https_urlopen", _no_network)

    out = wt._face_landmarker_model_path()
    assert out == cached
    assert call_count["n"] == 0


def test_face_landmarker_model_path_raises_on_download_failure(
    tmp_path, monkeypatch,
):
    """A 404 / network outage should produce a ``_WebcamSetupError``
    with a readable message — not a raw ``URLError`` traceback in
    the user's status bar."""
    import pytest
    from Imervue.puppet import webcam_tracker as wt

    monkeypatch.setattr(
        "Imervue.system.app_paths.app_dir",
        lambda: tmp_path,
    )
    def _boom(_url):   # noqa: ANN001
        raise OSError("simulated network failure")
    monkeypatch.setattr(wt, "_https_urlopen", _boom)

    with pytest.raises(wt._WebcamSetupError):
        wt._face_landmarker_model_path()


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
