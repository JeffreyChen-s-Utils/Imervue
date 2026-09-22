"""PIL Image <-> QImage conversion.

Both directions go through RGBA8888 and copy the pixel buffer, so the
result never aliases memory the other side may free.
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from PySide6.QtGui import QImage

_MODE_RGBA = "RGBA"


def pil_to_qimage(img: Image.Image) -> QImage:
    """Convert a PIL Image to an owned QImage (RGBA8888)."""
    if img.mode != _MODE_RGBA:
        img = img.convert(_MODE_RGBA)
    arr = np.array(img)
    h, w = arr.shape[:2]
    qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    # .copy() detaches from the numpy buffer — otherwise the QImage dies
    # the moment `arr` goes out of scope.
    return qimg.copy()


def qimage_to_pil(qimg: QImage) -> Image.Image:
    """Convert a QImage to a PIL RGBA Image."""
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
    return Image.fromarray(arr, _MODE_RGBA)
