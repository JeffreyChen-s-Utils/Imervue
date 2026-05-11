"""Frame capture + recording for the Puppet workspace.

* :func:`capture_canvas_image` — pull the current GL framebuffer off
  a :class:`PuppetCanvas` as a QImage. The canvas's
  ``grabFramebuffer`` must run after a paint cycle so the texture
  upload has actually happened.
* :class:`RecordingSession` — QTimer-driven frame loop that writes to
  a GIF / MP4 / WebM via imageio (an existing project dep).

Both the capture and record paths require the canvas to have an
active GL context — tests skip the actual file write but exercise
the API contract.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

    from puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.recorder")

DEFAULT_RECORD_FPS: int = 30


class CaptureError(RuntimeError):
    """Raised when a frame capture fails (typically because the canvas
    has no active GL context yet)."""


def capture_canvas_image(canvas: PuppetCanvas) -> QImage:
    """Return the current GL framebuffer of ``canvas`` as a QImage.

    May raise :class:`CaptureError` for the empty / null wrapper case
    *or* propagate ``OpenGL.error.GLError`` / ``RuntimeError`` if the
    underlying GL context isn't current — both happen on CI machines
    that don't have a live display. Callers wrap accordingly.
    """
    image = canvas.grabFramebuffer()
    if image is None or image.isNull():
        raise CaptureError("canvas has no captured framebuffer yet")
    return image


def save_canvas_png(canvas: PuppetCanvas, path: str | Path) -> bool:
    """Capture ``canvas`` and save as PNG. Returns ``True`` on success.

    Catches everything the GL stack might throw — CaptureError,
    OpenGL.error.GLError (no active context on headless CI),
    RuntimeError (shiboken-style teardown), and generic Exception (PIL
    / image-save backends raise mixed types). The user will retry
    after a real paint cycle anyway.
    """
    try:
        image = capture_canvas_image(canvas)
    except (CaptureError, RuntimeError, Exception) as exc:   # noqa: BLE001
        logger.warning("capture failed: %s", exc)
        return False
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        return bool(image.save(str(p), "PNG"))
    except Exception as exc:   # noqa: BLE001
        logger.warning("png save failed: %s", exc)
        return False


class RecordingSession(QObject):
    """Timer-driven recording of canvas frames to a video / gif file.

    Wraps imageio's writer; one frame is appended per timer tick so
    the exported clip's framerate matches ``fps`` regardless of how
    fast the canvas itself paints.
    """

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._writer = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._path: str | None = None
        self._fps: int = DEFAULT_RECORD_FPS

    def is_recording(self) -> bool:
        return self._writer is not None

    def start(
        self, path: str | Path, *, fps: int = DEFAULT_RECORD_FPS,
    ) -> bool:
        if self.is_recording():
            return False
        try:
            import imageio.v3 as iio  # noqa: F401 - probe import
            import imageio
        except ImportError:
            self.failed.emit("imageio is not installed")
            return False
        try:
            self._writer = imageio.get_writer(str(path), fps=int(fps))
        except (OSError, ValueError) as exc:
            # imageio raises ValueError for directories / unknown
            # extensions and OSError for permission / path failures —
            # treat both as a clean failure rather than crashing the
            # workspace.
            logger.warning("recording open failed: %s", exc)
            self.failed.emit(str(exc))
            return False
        self._path = str(path)
        self._fps = max(1, int(fps))
        self._timer.setInterval(int(1000 / self._fps))
        self._timer.start()
        return True

    def stop(self) -> str | None:
        if not self.is_recording():
            return None
        self._timer.stop()
        try:
            self._writer.close()
        except Exception as exc:   # noqa: BLE001 - imageio raises a zoo
            logger.warning("recording close failed: %s", exc)
        out = self._path
        self._writer = None
        self._path = None
        if out is not None:
            self.finished.emit(out)
        return out

    # ---- internals ----------------------------------------------------

    def _on_tick(self) -> None:
        if not self.is_recording():
            return
        try:
            image = capture_canvas_image(self._canvas)
        except (CaptureError, RuntimeError, Exception):   # noqa: BLE001
            # GL not ready yet on this tick — skip the frame; the
            # writer keeps running so the next ready frame extends the
            # clip naturally.
            return
        frame = _qimage_to_rgb_array(image)
        if frame is None:
            return
        try:
            self._writer.append_data(frame)
        except Exception as exc:   # noqa: BLE001 - imageio writer error surface
            logger.warning("recording append failed: %s", exc)
            self.stop()
            self.failed.emit(str(exc))


def _qimage_to_rgb_array(image: QImage):
    """Convert ``image`` to an HxWx3 uint8 ndarray. Returns ``None``
    if the conversion isn't possible (degenerate image)."""
    from PySide6.QtGui import QImage as _QImage
    import numpy as np
    if image.format() != _QImage.Format.Format_RGB888:
        image = image.convertToFormat(_QImage.Format.Format_RGB888)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return None
    ptr = image.constBits()
    if hasattr(ptr, "setsize"):
        ptr.setsize(image.sizeInBytes())
    arr = np.frombuffer(bytes(ptr), dtype=np.uint8).reshape(
        (height, image.bytesPerLine()),
    )
    # Drop padding past width*3
    return arr[:, : width * 3].reshape((height, width, 3)).copy()
