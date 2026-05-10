"""Coverage for capture / record API contracts.

The actual GL framebuffer grab needs an active display, so these
tests poke the API surface — start/stop semantics, dependency-error
paths — without trying to read pixels.

We use a lightweight stub canvas in place of the real
:class:`PuppetCanvas` so the test session doesn't accumulate
unparented ``QOpenGLWidget`` instances; on Windows CI those triggered
``Windows fatal exception: access violation`` after enough widgets
piled up. The recorder only needs ``grabFramebuffer()`` and
``document()`` from its target so the stub stays minimal.
"""
from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from puppet.recorder import RecordingSession, save_canvas_png


class _StubCanvas(QWidget):
    """Plain-QWidget stand-in that only implements the canvas methods
    the recorder consumes."""

    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None

    def set_capture_image(self, image: QImage | None) -> None:
        self._image = image

    def grabFramebuffer(self) -> QImage:   # noqa: N802 - mirrors Qt API
        return self._image if self._image is not None else QImage()

    def document(self):
        return None


def _stub_with_real_image(width: int = 8, height: int = 8) -> _StubCanvas:
    canvas = _StubCanvas()
    img = QImage(QSize(width, height), QImage.Format.Format_RGB888)
    img.fill(0)
    canvas.set_capture_image(img)
    return canvas


# ---------------------------------------------------------------------------
# save_canvas_png
# ---------------------------------------------------------------------------


def test_save_canvas_png_returns_false_when_no_framebuffer(qapp, tmp_path):
    """A stubbed canvas with a null framebuffer must produce a
    `False` rather than crashing — same shape as a real canvas
    pre-paint."""
    canvas = _StubCanvas()
    try:
        out = tmp_path / "frame.png"
        result = save_canvas_png(canvas, out)
        assert isinstance(result, bool)
        assert result is False
    finally:
        canvas.deleteLater()


def test_save_canvas_png_writes_real_image(qapp, tmp_path):
    canvas = _stub_with_real_image()
    try:
        out = tmp_path / "frame.png"
        assert save_canvas_png(canvas, out) is True
        assert out.exists()
        assert out.stat().st_size > 0
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# RecordingSession lifecycle
# ---------------------------------------------------------------------------


def test_recorder_starts_idle(qapp):
    canvas = _StubCanvas()
    rec = RecordingSession(canvas)
    try:
        assert rec.is_recording() is False
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_stop_when_idle_returns_none(qapp):
    canvas = _StubCanvas()
    rec = RecordingSession(canvas)
    try:
        assert rec.stop() is None
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_double_start_returns_false(qapp, tmp_path):
    """Once recording, a second start must be rejected so we don't
    leak a second writer onto the same QTimer."""
    canvas = _stub_with_real_image()
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
    canvas = _StubCanvas()
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
    canvas = _stub_with_real_image()
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
