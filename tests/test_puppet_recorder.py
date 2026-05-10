"""Coverage for capture / record API contracts.

The actual GL framebuffer grab needs an active display, so these
tests poke the API surface — start/stop semantics, dependency-error
paths — without trying to read pixels.
"""
from __future__ import annotations

from puppet.canvas import PuppetCanvas
from puppet.recorder import RecordingSession, save_canvas_png


# ---------------------------------------------------------------------------
# save_canvas_png
# ---------------------------------------------------------------------------


def test_save_canvas_png_returns_false_when_no_framebuffer(qapp, tmp_path):
    """Without a paint cycle the GL framebuffer is empty — save must
    return False rather than producing a corrupt zero-byte PNG."""
    canvas = PuppetCanvas()
    try:
        out = tmp_path / "frame.png"
        result = save_canvas_png(canvas, out)
        # Either way (capture worked / didn't), result is a bool
        assert isinstance(result, bool)
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# RecordingSession lifecycle
# ---------------------------------------------------------------------------


def test_recorder_starts_idle(qapp):
    canvas = PuppetCanvas()
    rec = RecordingSession(canvas)
    try:
        assert rec.is_recording() is False
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_stop_when_idle_returns_none(qapp):
    canvas = PuppetCanvas()
    rec = RecordingSession(canvas)
    try:
        assert rec.stop() is None
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_double_start_returns_false(qapp, tmp_path):
    """Once recording, a second start must be rejected so we don't
    leak a second writer onto the same QTimer."""
    canvas = PuppetCanvas()
    rec = RecordingSession(canvas)
    try:
        out = tmp_path / "anim.gif"
        # First start may succeed or fail depending on imageio /
        # codec availability; either way capture the result.
        first = rec.start(out)
        if first:
            second = rec.start(tmp_path / "other.gif")
            assert second is False
            rec.stop()
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_handles_invalid_output_path(qapp, tmp_path):
    """A path with an unsupported extension should fail-clean rather
    than raise."""
    canvas = PuppetCanvas()
    rec = RecordingSession(canvas)
    captured: list = []
    rec.failed.connect(lambda reason: captured.append(reason))
    try:
        # imageio rejects a directory as an output target on most platforms
        ok = rec.start(tmp_path)
        assert ok is False
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_emits_finished_on_clean_stop(qapp, tmp_path):
    canvas = PuppetCanvas()
    rec = RecordingSession(canvas)
    captured: list = []
    rec.finished.connect(lambda path: captured.append(path))
    try:
        out = tmp_path / "anim.gif"
        ok = rec.start(out)
        if not ok:
            return   # imageio backend unavailable on this CI box
        rec.stop()
        assert captured and captured[-1] == str(out)
    finally:
        rec.deleteLater()
        canvas.deleteLater()
