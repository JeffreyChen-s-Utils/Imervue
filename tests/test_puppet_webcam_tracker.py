"""Smoke tests for WebcamTracker — the actual mediapipe / OpenCV
pipeline isn't reachable in CI (no camera, optional deps), so we only
exercise the API contract: construction, toggle, graceful degrade
when imports fail.
"""
from __future__ import annotations

from puppet.canvas import PuppetCanvas
from puppet.webcam_tracker import WebcamTracker


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
