"""Shared look of the ``OverlayPainter`` layers.

Font families and colours used by more than one overlay mixin, plus the
numpy → ``QPixmap`` handoff that the filmstrip and both loupes share.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage, QPixmap

_FONT_SEGOE_UI = "Segoe UI"
_FONT_CONSOLAS = "Consolas"
_ERROR_PANEL_RGBA = (95, 28, 28, 210)


def _rgba_to_pixmap(arr: np.ndarray) -> QPixmap:
    """Convert an H×W×4 uint8 RGBA array into a detached :class:`QPixmap`.

    ``.copy()`` detaches the ``QImage`` from the numpy buffer before the array
    can be freed (the established project idiom for numpy → Qt image handoff).
    """
    contiguous = np.ascontiguousarray(arr)
    height, width = contiguous.shape[:2]
    qimg = QImage(contiguous.data, width, height, width * 4,
                  QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimg)
