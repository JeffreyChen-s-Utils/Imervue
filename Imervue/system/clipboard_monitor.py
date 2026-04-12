"""
Clipboard image monitor — ShareX-style PrintScreen → annotation flow.

Listens for image data appearing on the system clipboard and emits a
``image_captured`` signal carrying a PIL Image. The main window connects
that signal to the annotation dialog so a user can hit PrintScreen and
immediately mark up the screenshot.

Design notes
------------
- The monitor is *always* installed when the main window starts, but it
  only acts on clipboard events when ``enabled`` is True. The toggle is
  persisted in ``user_setting_dict["annotation_clipboard_monitor_enabled"]``
  so the user's choice survives restarts.
- Qt's ``QClipboard.dataChanged`` fires every time the clipboard contents
  change, including when *we* set the clipboard ourselves (e.g. the
  annotation dialog's "Copy" button). We deduplicate by hashing the raw
  image bytes — repeated identical images are ignored.
- Images on the clipboard arrive as ``QImage`` and are converted to PIL
  on the way out. Conversion happens in this module (not the dialog) so
  the rest of the app sees a uniform PIL surface.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QClipboard, QImage
from PySide6.QtWidgets import QApplication

from Imervue.user_settings.user_setting_dict import (
    schedule_save, user_setting_dict,
)

logger = logging.getLogger("Imervue.clipboard_monitor")

SETTING_KEY = "annotation_clipboard_monitor_enabled"


def _qimage_to_pil(qimg: QImage) -> Image.Image:
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
    return Image.fromarray(arr, "RGBA")


class ClipboardMonitor(QObject):
    """Watch the system clipboard and emit ``image_captured`` for new images.

    Use ``set_enabled()`` to flip the monitor on/off — the underlying Qt
    signal stays connected either way; the gate is checked when each event
    fires. This avoids subtle issues around connect/disconnect ordering when
    the toggle is flipped while a dataChanged event is in flight.
    """

    image_captured = Signal(object)  # emits a PIL.Image.Image

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._enabled: bool = bool(
            user_setting_dict.get(SETTING_KEY, False)
        )
        self._last_hash: Optional[str] = None
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self._on_clipboard_changed)

    # ---------- enable / disable ----------

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        user_setting_dict[SETTING_KEY] = enabled
        schedule_save()
        # Reset dedup so the next event after re-enabling isn't suppressed
        # by a hash captured before the toggle was flipped.
        self._last_hash = None
        logger.info("clipboard monitor %s", "enabled" if enabled else "disabled")

    def toggle(self) -> bool:
        self.set_enabled(not self._enabled)
        return self._enabled

    # ---------- manual paste (used by "Paste from clipboard" menu) ----------

    def grab_current_image(self) -> Optional[Image.Image]:
        """Return the current clipboard image as PIL, or None if not an image.

        Bypasses the enabled-check and the dedup hash — this is the explicit
        "user clicked Paste" path, where suppression would be surprising.
        """
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return None
        qimg = clipboard.image(QClipboard.Mode.Clipboard)
        if qimg is None or qimg.isNull():
            return None
        try:
            return _qimage_to_pil(qimg)
        except Exception:
            logger.exception("clipboard image conversion failed")
            return None

    # ---------- internal ----------

    def _on_clipboard_changed(self) -> None:
        if not self._enabled:
            return
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        mime = clipboard.mimeData(QClipboard.Mode.Clipboard)
        if mime is None or not mime.hasImage():
            return
        qimg = clipboard.image(QClipboard.Mode.Clipboard)
        if qimg is None or qimg.isNull():
            return
        try:
            pil = _qimage_to_pil(qimg)
        except Exception:
            logger.exception("clipboard image conversion failed")
            return

        digest = hashlib.md5(pil.tobytes()).hexdigest()
        if digest == self._last_hash:
            return
        self._last_hash = digest

        logger.info(
            "clipboard image captured: %dx%d", pil.width, pil.height
        )
        try:
            self.image_captured.emit(pil)
        except Exception:
            logger.exception("image_captured handler raised")
