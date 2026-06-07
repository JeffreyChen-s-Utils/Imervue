"""Shared widgets, constants and icon helpers for the dock panels."""
from __future__ import annotations


import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QSlider,
    QToolButton,
)


_SWATCH_PX = 22

# Restore-from-transparent fallbacks used when the user toggles a
# slot to ``None`` without ever having set a colour first. Black for
# FG and white for BG mirror the historical paint defaults.
DEFAULT_FG_FALLBACK = (0, 0, 0)
DEFAULT_BG_FALLBACK = (255, 255, 255)

# Style sheet shared by the dim "hint" / placeholder labels in
# multiple docks. Module-level so a future palette change updates
# every callsite at once.
_HINT_LABEL_STYLE = "color: #888;"

def _slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    return s


def _make_swatch_button() -> QToolButton:
    btn = QToolButton()
    btn.setFixedSize(_SWATCH_PX, _SWATCH_PX)
    btn.setAutoRaise(False)
    return btn


def _paint_swatch(
    button: QToolButton,
    rgb: tuple[int, int, int] | None,
) -> None:
    """Render a colour-chip icon on ``button``.

    ``rgb=None`` represents "transparent / no colour" and renders a
    grey checker pattern with a red diagonal slash — the same idiom
    Photoshop /  / raster paint apps use for "no fill" so users can
    spot the transparent slot at a glance.
    """
    pix = QPixmap(_SWATCH_PX, _SWATCH_PX)
    if rgb is None:
        pix.fill(QColor(255, 255, 255))
        painter = QPainter(pix)
        # Light-grey checker pattern.
        cell = 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 200, 200))
        for y in range(0, _SWATCH_PX, cell):
            for x in range(0, _SWATCH_PX, cell):
                if ((x // cell) + (y // cell)) % 2 == 0:
                    painter.drawRect(x, y, cell, cell)
        # Red slash for the universal "no colour" affordance.
        from PySide6.QtGui import QPen
        pen = QPen(QColor(220, 40, 40))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(2, _SWATCH_PX - 3, _SWATCH_PX - 3, 2)
        painter.setPen(QColor(0, 0, 0, 120))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, _SWATCH_PX - 1, _SWATCH_PX - 1)
        painter.end()
    else:
        pix.fill(QColor(*rgb))
        painter = QPainter(pix)
        painter.setPen(QColor(0, 0, 0, 80))
        painter.drawRect(0, 0, _SWATCH_PX - 1, _SWATCH_PX - 1)
        painter.end()
    button.setIcon(pix)
    button.setIconSize(pix.size())


# ---------------------------------------------------------------------------
# Layer-row presentation helpers
# ---------------------------------------------------------------------------


_LAYER_LABEL_GLYPHS = {
    "red": "🟥",
    "orange": "🟧",
    "yellow": "🟨",
    "green": "🟩",
    "blue": "🟦",
    "violet": "🟪",
    "grey": "⬜",
}


def _label_with_color_chip(layer) -> str:
    """Return ``layer.name`` prefixed with the colour-label glyph.

    The glyph approach keeps the LayerDock readable in plain-text
    accessibility tools (no custom QStandardItem needed), and the
    chip survives the existing ``itemChanged`` rename path because
    Qt always presents the full string back to ``_on_item_changed``.
    """
    label = getattr(layer, "color_label", None)
    name = layer.name
    glyph = _LAYER_LABEL_GLYPHS.get(label or "")
    if glyph is None:
        return name
    return f"{glyph} {name}"


def _strip_color_chip(text: str) -> str:
    """Remove the leading colour-chip glyph + space from ``text``.

    Inverse of :func:`_label_with_color_chip`. Keeps the persisted
    layer name free of emoji even after the user inline-edits a row
    that already had a chip prefix.
    """
    for glyph in _LAYER_LABEL_GLYPHS.values():
        prefix = f"{glyph} "
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _array_to_icon(thumb: np.ndarray) -> QIcon:
    """Wrap an HxWx4 RGBA buffer into a QIcon for the LayerDock list."""
    h, w = thumb.shape[:2]
    qimage = QImage(
        bytes(thumb.tobytes()),
        w, h, w * 4, QImage.Format.Format_RGBA8888,
    )
    return QIcon(QPixmap.fromImage(qimage))
