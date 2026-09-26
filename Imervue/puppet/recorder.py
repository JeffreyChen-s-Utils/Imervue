"""Frame capture + recording for the Puppet workspace.

* :func:`capture_canvas_image` — render just the character of a
  :class:`PuppetCanvas` off-screen (the streaming outputs' path), without
  the editor's checker backdrop, selection overlay, zoom or pan.
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

from OpenGL.error import GLError
from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.recorder")

DEFAULT_RECORD_FPS: int = 30

# A capture keeps the rig's own size (its long side capped at what an off-screen
# framebuffer reliably allows) on a transparent background. A recording fits the
# rig into 1080 pixels on white: GIF / MP4 / WebM frames here carry no alpha, and
# sizes are multiples of ffmpeg's 16-pixel macro block, which imageio would
# otherwise stretch the frame to.
CAPTURE_LONG_SIDE: int = 4096
RECORD_LONG_SIDE: int = 1080
_VIDEO_BLOCK: int = 16
_TRANSPARENT = (0.0, 0.0, 0.0, 0.0)
_WHITE = (1.0, 1.0, 1.0, 1.0)


class CaptureError(RuntimeError):
    """Raised when a frame capture fails (typically because the canvas
    has no active GL context yet)."""


def frame_size(
    doc_size: tuple[float, float], long_side: int, multiple: int = 1,
) -> tuple[int, int]:
    """The document size scaled down so its long side is at most ``long_side``,
    each side rounded to a positive multiple of ``multiple``."""
    width, height = (max(1, round(float(v))) for v in doc_size)
    longest = max(width, height)

    def fit(value: int) -> int:
        scaled = value * long_side // longest if longest > long_side else value
        return max(multiple, scaled // multiple * multiple)

    return fit(width), fit(height)


def capture_canvas_image(
    canvas: PuppetCanvas,
    *,
    long_side: int = CAPTURE_LONG_SIDE,
    background_rgba: tuple[float, float, float, float] = _TRANSPARENT,
    multiple: int = 1,
) -> QImage:
    """Render the loaded character off-screen and return it as a QImage.

    The image is the document fitted into :func:`frame_size`, on
    ``background_rgba``, without the editor's checker backdrop, selection
    overlay, zoom or pan. Raises :class:`CaptureError` when no document is
    loaded or the render fails, and propagates ``OpenGL.error.GLError`` /
    ``RuntimeError`` when there is no GL context (CI machines without a
    display). Callers wrap accordingly.
    """
    document = canvas.document()
    if document is None:
        raise CaptureError("no puppet is loaded")
    width, height = frame_size(document.size, long_side, multiple)
    image = canvas.render_offscreen_puppet(width, height, background_rgba=background_rgba)
    if image is None or image.isNull():
        raise CaptureError("the puppet could not be rendered off-screen")
    return image


def save_canvas_png(canvas: PuppetCanvas, path: str | Path) -> bool:
    """Capture ``canvas`` and save as PNG. Returns ``True`` on success.

    A failed capture — ``CaptureError`` (no framebuffer yet),
    ``OpenGL.error.GLError`` (no active context on headless CI) or
    ``RuntimeError`` (shiboken-style teardown) — and a destination folder
    that cannot be created are logged and return ``False``; so does a
    ``QImage.save`` that reports failure. The user will retry after a real
    paint cycle anyway.
    """
    try:
        image = capture_canvas_image(canvas)
    except (GLError, RuntimeError) as exc:   # includes CaptureError
        logger.warning("capture failed: %s", exc)
        return False
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("png save failed: %s", exc)
        return False
    if not image.save(str(p), "PNG"):
        logger.warning("png save failed: %s", p)
        return False
    return True


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
            image = capture_canvas_image(
                self._canvas, long_side=RECORD_LONG_SIDE,
                background_rgba=_WHITE, multiple=_VIDEO_BLOCK,
            )
        except (GLError, RuntimeError):   # includes CaptureError
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


def save_spritesheet_from_qimages(images, path, max_cols: int = 8) -> tuple[int, int]:
    """Pack recorded canvas frames (QImages) into one spritesheet PNG.

    Bridges the recorder's QImage→array conversion to the pure spritesheet
    composer; returns ``(cols, rows)``. Degenerate frames are skipped, and an
    empty / all-degenerate sequence raises ``ValueError``.
    """
    from Imervue.puppet.spritesheet import save_spritesheet
    frames = [arr for img in images if (arr := _qimage_to_rgb_array(img)) is not None]
    if not frames:
        raise ValueError("no convertible frames to write")
    return save_spritesheet(frames, path, max_cols=max_cols)


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
