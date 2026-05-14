"""Pump puppet canvas frames into a system virtual camera.

When the toggle is on, ``pyvirtualcam`` opens the platform virtual
camera (OBS Virtual Camera on Windows / macOS, v4l2loopback on
Linux) at the puppet document's canvas size. A QTimer grabs frames
off the GL canvas and pushes them to the camera at the configured
FPS. Any video-conferencing or streaming tool that can pick a webcam
source then sees the puppet as a regular camera input.

Optional dep — ``pyvirtualcam`` is listed in
:mod:`puppet.requirements`. The Qt wrapper degrades cleanly when the
module isn't importable so a vanilla install can still use the rest
of the puppet plugin.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.recorder import CaptureError, capture_canvas_image

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.virtual_camera")

DEFAULT_FPS: int = 30

# Cap the longest side of the virtual-camera frame. Live2D source
# canvases are routinely 3000–8000 px tall (March 7th is 3503×7777),
# which DirectShow virtual-camera drivers reject outright and which
# wastes downstream bandwidth in any streaming pipeline. 1080 covers
# every common streaming aspect (1080p landscape, 1920×1080 portrait,
# 1080×1920 for vertical platforms) — anything taller gets scaled
# down proportionally before the camera is opened.
MAX_OUTPUT_DIMENSION: int = 1080


def _widget_capture_size(widget) -> tuple[int, int]:
    """Pixel-space size of ``widget`` (Qt logical size × devicePixelRatio).

    The QOpenGLWidget framebuffer ``grabFramebuffer`` hands back is
    at this *physical* size, not the logical Qt size — failing to
    apply the DPR scale on HiDPI screens would also produce stretched
    output. Pure helper so the streaming-outputs scaler can be
    unit-tested with a stand-in widget."""
    if widget is None:
        return 0, 0
    ratio = (
        widget.devicePixelRatioF()
        if hasattr(widget, "devicePixelRatioF") else 1.0
    )
    return int(widget.width() * ratio), int(widget.height() * ratio)


def _scale_for_streaming(width: int, height: int) -> tuple[int, int]:
    """Scale ``(width, height)`` so the longest side is at most
    :data:`MAX_OUTPUT_DIMENSION`, preserving aspect ratio.

    Pure helper so the resolution cap can be unit-tested without the
    pyvirtualcam dep. Returns ``(width, height)`` unchanged when both
    are already within the limit; rounds the smaller dimension to an
    even integer (some virtual-camera drivers reject odd widths)."""
    if width <= 0 or height <= 0:
        return width, height
    longest = max(width, height)
    if longest <= MAX_OUTPUT_DIMENSION:
        return width, height
    scale = MAX_OUTPUT_DIMENSION / longest
    new_w = max(2, int(round(width * scale)) & ~1)
    new_h = max(2, int(round(height * scale)) & ~1)
    return new_w, new_h


class VirtualCameraOutput(QObject):
    """Stream the canvas to a virtual camera device.

    Construction is cheap — the ``pyvirtualcam`` import and the
    device handle only materialise on :meth:`set_enabled(True)`. Off
    by default; toggle once for the workspace toolbar's "Virtual
    camera" action."""

    state_changed = Signal()

    def __init__(self, canvas: PuppetCanvas, parent=None, *, fps: int = DEFAULT_FPS):
        super().__init__(parent)
        self._canvas = canvas
        self._fps = max(1, int(fps))
        self._enabled = False
        self._camera = None
        self._anchor: float = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / self._fps))
        self._timer.timeout.connect(self._on_tick)

    def is_enabled(self) -> bool:
        return self._enabled

    def fps(self) -> int:
        return self._fps

    def set_fps(self, fps: int) -> None:
        """Change the target frame rate. Takes effect on the next
        enable — pyvirtualcam's frame size + fps are baked in at
        ``Camera`` construction."""
        self._fps = max(1, int(fps))
        self._timer.setInterval(int(1000 / self._fps))

    def set_enabled(self, enabled: bool) -> bool:
        if enabled == self._enabled:
            return True
        if enabled:
            ok = self._start()
            if not ok:
                self._enabled = False
                self.state_changed.emit()
                return False
        else:
            self._stop()
        self._enabled = bool(enabled)
        self.state_changed.emit()
        return True

    def shutdown(self) -> None:
        self._stop()

    # ---- start / stop --------------------------------------------------

    def _start(self) -> bool:  # pragma: no cover - needs pyvirtualcam + display
        document = self._canvas.document()
        if document is None:
            logger.info("virtual camera: no document — refusing to start")
            return False
        try:
            import pyvirtualcam
        except ImportError:
            logger.info("pyvirtualcam not installed; virtual camera unavailable")
            return False
        # Match the camera's aspect ratio to what's actually on the
        # screen — the GL framebuffer we capture each tick is at the
        # widget's pixel size, not the document's logical canvas
        # size. Opening the camera at the document aspect (e.g. the
        # 3503×7777 portrait Cubism canvas) while the user is looking
        # at a 1200×800 landscape widget would force IgnoreAspectRatio
        # scaling and visibly stretch the puppet. "Stream what you
        # see" is also the mental model most users expect.
        src_w, src_h = _widget_capture_size(self._canvas)
        if src_w <= 0 or src_h <= 0:
            src_w, src_h = document.size
        width, height = _scale_for_streaming(src_w, src_h)
        try:
            self._camera = pyvirtualcam.Camera(
                width=int(width), height=int(height), fps=self._fps,
                fmt=pyvirtualcam.PixelFormat.RGB,
            )
        except Exception as exc:   # noqa: BLE001 - pyvirtualcam errors vary by backend
            logger.warning("virtual camera open failed: %s", exc)
            return False
        self._anchor = time.monotonic()
        self._timer.start()
        logger.info(
            "virtual camera streaming %dx%d @ %d fps via %s",
            int(width), int(height), self._fps, self._camera.device,
        )
        return True

    def _stop(self) -> None:  # pragma: no cover - needs pyvirtualcam
        self._timer.stop()
        cam = self._camera
        self._camera = None
        if cam is None:
            return
        try:
            cam.close()
        except Exception as exc:   # noqa: BLE001 - close paths vary
            logger.warning("virtual camera close failed: %s", exc)

    # ---- frame pump ----------------------------------------------------

    def _on_tick(self) -> None:  # pragma: no cover - needs pyvirtualcam + display
        if self._camera is None:
            return
        try:
            image = capture_canvas_image(self._canvas)
        except (CaptureError, RuntimeError, Exception):   # noqa: BLE001
            return
        frame = _qimage_to_rgb_array(image, self._camera.width, self._camera.height)
        if frame is None:
            return
        try:
            self._camera.send(frame)
            self._camera.sleep_until_next_frame()
        except Exception as exc:   # noqa: BLE001 - same surface as open
            logger.warning("virtual camera send failed: %s", exc)
            self._stop()


def _qimage_to_rgb_array(image, target_width: int, target_height: int):
    """Convert a QImage to an HxWx3 uint8 numpy array sized to
    exactly ``(target_height, target_width)``.

    Aspect ratio is **preserved** — the source image is scaled to
    fit within the target box (Qt's KeepAspectRatio), then the
    result is centred onto a black-filled buffer of the target size
    if the aspect ratios don't match. This is the fix for the
    "puppet looks stretched in OBS" report: the camera is opened
    at the widget's aspect ratio at start, but if the user resizes
    the window mid-stream the captured framebuffer no longer
    matches; preserving aspect prevents the distortion at the cost
    of black bars on resize."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage as _QImage
    if target_width <= 0 or target_height <= 0:
        return None
    if image.width() != target_width or image.height() != target_height:
        image = image.scaled(
            target_width, target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    if image.format() != _QImage.Format.Format_RGB888:
        image = image.convertToFormat(_QImage.Format.Format_RGB888)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return None
    ptr = image.constBits()
    if hasattr(ptr, "setsize"):
        ptr.setsize(image.sizeInBytes())
    scaled = np.frombuffer(bytes(ptr), dtype=np.uint8).reshape(
        (height, image.bytesPerLine()),
    )
    scaled = scaled[:, : width * 3].reshape((height, width, 3)).copy()
    if width == target_width and height == target_height:
        return scaled
    # Aspect didn't match — centre the scaled image on a black canvas
    # at the camera's target size. Streamers who want a chroma-key
    # background can run an OBS Color Key filter on the matte
    # colour, OR resize the puppet workspace tab before enabling
    # the virtual camera so the aspects line up.
    canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    off_x = (target_width - width) // 2
    off_y = (target_height - height) // 2
    canvas[off_y:off_y + height, off_x:off_x + width] = scaled
    return canvas
