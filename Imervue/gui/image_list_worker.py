"""Decode detached thumbnail images away from the GUI thread."""

from __future__ import annotations
import os
from pathlib import Path
from PIL import Image
from PySide6.QtCore import (
    QRunnable,
    Signal,
    QObject,
)
from PySide6.QtGui import QImage
from Imervue.image.shown import as_shown_8bit
from Imervue.image.dimensions import image_dimensions
from Imervue.image.formats import ensure_pillow_opener
from Imervue.image.orientation import exif_orientation
from Imervue.image.read_errors import IMAGE_READ_ERRORS

from Imervue.gui.image_list_values import _THUMB_SIZE, logger


class _ThumbWorkerSignals(QObject):
    # path, img, w, h, size_kb, mtime, ok. Carries a QImage (safe to build on a
    # worker thread) — NOT a QPixmap, which is a QPaintDevice and undefined to
    # create off the GUI thread. The receiving slot converts it. ``ok`` is False
    # when the stat/decode failed (transient read race), so the model can retry
    # instead of caching a permanent placeholder or stranding the in-flight row.
    done = Signal(str, QImage, int, int, float, float, bool)


class _ThumbWorker(QRunnable):
    """Fetch file stat + a scaled thumbnail off the UI thread."""

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = _ThumbWorkerSignals()

    def run(self) -> None:
        try:
            stat = os.stat(self.path)
            size_kb = stat.st_size / 1024
            mtime = stat.st_mtime
            ensure_pillow_opener(Path(self.path).suffix)
            with Image.open(self.path) as src:
                w, h = src.size
                code = exif_orientation(src)
                src.thumbnail((_THUMB_SIZE, _THUMB_SIZE), Image.Resampling.LANCZOS)
                im = as_shown_8bit(src, code)
            # The upright size, and the developed size for RAW (Pillow sees its preview).
            w, h = image_dimensions(self.path) or (w, h)
            data = im.tobytes("raw", "RGBA")
            qimg = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
            # .copy() detaches from the soon-freed `data` buffer; the GUI
            # thread turns this QImage into a QPixmap in _on_fetched.
            img = qimg.copy()
        # Any failure must still emit so the model clears the in-flight marker
        # and can retry rather than leaving the row stuck forever. A null QImage
        # tells the slot to build the placeholder pixmap on the GUI thread.
        except IMAGE_READ_ERRORS:  # missing or unreadable file: expected
            self.signals.done.emit(self.path, QImage(), 0, 0, 0.0, 0.0, False)
            return
        except Exception:  # noqa: BLE001 - worker boundary logs the bug and still emits
            logger.exception("Thumbnail worker failed for %s", self.path)
            self.signals.done.emit(self.path, QImage(), 0, 0, 0.0, 0.0, False)
            return

        self.signals.done.emit(self.path, img, w, h, size_kb, mtime, True)
