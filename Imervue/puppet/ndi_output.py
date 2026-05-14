"""Broadcast the puppet canvas as an NDI source.

NDI (Network Device Interface, NewTek) is the de-facto standard for
low-latency video routing between video-production tools (OBS,
vMix, Wirecast, …). When this output is on, any NDI receiver on the
same subnet sees the puppet as ``IMERVUE (Puppet)``.

Optional dep — ``ndi-python`` is the actively-maintained Python
binding. The wrapper lazy-imports it so the rest of the plugin stays
usable on machines without the NDI runtime.

Spout (Windows-only) and Syphon (macOS-only) intentionally not
covered here — their Python bindings are abandoned. Users who need
GPU-shared-texture-grade latency should pair the virtual camera with
OBS instead.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.recorder import CaptureError, capture_canvas_image

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.ndi_output")

DEFAULT_FPS: int = 30
DEFAULT_SOURCE_NAME: str = "Imervue Puppet"

# Same cap as the virtual-camera output for the same reason — see
# ``virtual_camera.MAX_OUTPUT_DIMENSION``. NDI itself doesn't reject
# huge frames, but a Cubism-native 3503×7777 source saturates a
# 1 Gbps LAN and chokes any downstream OBS receiver.
from Imervue.puppet.virtual_camera import _scale_for_streaming   # noqa: E402


class NDIOutput(QObject):
    """Stream the canvas as an NDI source.

    Lazy-imports ``NDIlib`` (the ndi-python module name) on
    :meth:`set_enabled(True)` so a missing NDI SDK doesn't break
    plugin load. When the SDK is missing, :meth:`set_enabled` returns
    ``False`` and the toggle reverts."""

    state_changed = Signal()

    def __init__(
        self,
        canvas: PuppetCanvas,
        parent=None,
        *,
        fps: int = DEFAULT_FPS,
        source_name: str = DEFAULT_SOURCE_NAME,
    ):
        super().__init__(parent)
        self._canvas = canvas
        self._fps = max(1, int(fps))
        self._source_name = str(source_name)
        self._enabled = False
        self._ndi = None
        self._sender = None
        self._anchor: float = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / self._fps))
        self._timer.timeout.connect(self._on_tick)

    def is_enabled(self) -> bool:
        return self._enabled

    def fps(self) -> int:
        return self._fps

    def set_fps(self, fps: int) -> None:
        self._fps = max(1, int(fps))
        self._timer.setInterval(int(1000 / self._fps))

    def source_name(self) -> str:
        return self._source_name

    def set_source_name(self, name: str) -> None:
        """Change the NDI source name that receivers see. Takes
        effect on the next enable — NDI sender names are baked at
        ``send_create`` time."""
        self._source_name = str(name) or DEFAULT_SOURCE_NAME

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

    def _start(self) -> bool:  # pragma: no cover - needs NDI runtime
        if self._canvas.document() is None:
            logger.info("NDI: no document — refusing to start")
            return False
        try:
            import NDIlib as ndi  # noqa: N813  # vendor lib name is PascalCase
        except ImportError:
            logger.info("ndi-python not installed; NDI output unavailable")
            return False
        try:
            if not ndi.initialize():
                logger.warning("NDI initialize failed")
                return False
            create = ndi.SendCreate()
            create.ndi_name = self._source_name
            sender = ndi.send_create(create)
            if sender is None:
                ndi.destroy()
                logger.warning("NDI send_create returned None")
                return False
        except Exception as exc:   # noqa: BLE001 - NDI surfaces vary
            logger.warning("NDI open failed: %s", exc)
            return False
        self._ndi = ndi
        self._sender = sender
        self._anchor = time.monotonic()
        self._timer.start()
        logger.info("NDI source %r is broadcasting at %d fps", self._source_name, self._fps)
        return True

    def _stop(self) -> None:  # pragma: no cover - needs NDI runtime
        self._timer.stop()
        ndi = self._ndi
        sender = self._sender
        self._ndi = None
        self._sender = None
        if sender is not None and ndi is not None:
            try:
                ndi.send_destroy(sender)
            except Exception as exc:   # noqa: BLE001
                logger.warning("NDI send_destroy failed: %s", exc)
        if ndi is not None:
            try:
                ndi.destroy()
            except Exception as exc:   # noqa: BLE001
                logger.warning("NDI destroy failed: %s", exc)

    # ---- frame pump ----------------------------------------------------

    def _on_tick(self) -> None:  # pragma: no cover - needs NDI runtime
        if self._sender is None or self._ndi is None:
            return
        try:
            image = capture_canvas_image(self._canvas)
        except (CaptureError, RuntimeError, Exception):   # noqa: BLE001
            return
        target_w, target_h = _scale_for_streaming(image.width(), image.height())
        frame = _qimage_to_rgba_array(image, target_w, target_h)
        if frame is None:
            return
        try:
            video_frame = self._ndi.VideoFrameV2()
            video_frame.data = frame
            video_frame.FourCC = self._ndi.FOURCC_VIDEO_TYPE_RGBA
            self._ndi.send_send_video_v2(self._sender, video_frame)
        except Exception as exc:   # noqa: BLE001
            logger.warning("NDI send failed: %s", exc)
            self._stop()


def _qimage_to_rgba_array(image, target_width: int, target_height: int):
    """QImage → HxWx4 uint8 numpy scaled to ``(target_height,
    target_width)``. NDI expects RGBA frames — the alpha channel is
    preserved so receivers downstream can composite the puppet over
    their own backgrounds.

    Scaling happens here (rather than in ``_on_tick``) so a future
    fps / quality knob can swap the transformation mode without
    touching the rest of the pipeline."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage as _QImage
    if image.width() != target_width or image.height() != target_height:
        image = image.scaled(
            target_width, target_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    if image.format() != _QImage.Format.Format_RGBA8888:
        image = image.convertToFormat(_QImage.Format.Format_RGBA8888)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return None
    ptr = image.constBits()
    if hasattr(ptr, "setsize"):
        ptr.setsize(image.sizeInBytes())
    arr = np.frombuffer(bytes(ptr), dtype=np.uint8).reshape((height, image.bytesPerLine()))
    return arr[:, : width * 4].reshape((height, width, 4)).copy()
