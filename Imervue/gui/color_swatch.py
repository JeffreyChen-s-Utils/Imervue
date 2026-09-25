"""A button that shows a colour and opens the colour picker to change it."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QPushButton, QWidget

Rgb = tuple[int, int, int]


def swatch_style(rgb: Rgb) -> str:
    """Style sheet that fills a button with *rgb*."""
    r, g, b = rgb
    return f"background: rgb({r}, {g}, {b}); border: 1px solid #444; border-radius: 3px;"


def hex_name(rgb: Rgb) -> str:
    """``#RRGGBB`` for *rgb*, shown as the swatch's tooltip."""
    return "#{:02X}{:02X}{:02X}".format(*rgb)


class ColorSwatchButton(QPushButton):
    """Filled with its colour; a click opens the picker. :meth:`rgb` is the current colour."""

    def __init__(self, rgb: Rgb, parent: QWidget | None = None, *, title: str = "") -> None:
        super().__init__(parent)
        self._title = title
        self._rgb: Rgb = (0, 0, 0)
        self.setFixedHeight(24)
        self.set_rgb(rgb)
        self.clicked.connect(self._pick)

    def rgb(self) -> Rgb:
        """The colour the button shows."""
        return self._rgb

    def set_rgb(self, rgb: Rgb) -> None:
        """Show *rgb* (each channel clamped to 0-255)."""
        r, g, b = (max(0, min(255, int(c))) for c in rgb)
        self._rgb = (r, g, b)
        self.setStyleSheet(swatch_style(self._rgb))
        self.setToolTip(hex_name(self._rgb))

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(*self._rgb), self, self._title)
        if chosen.isValid():
            self.set_rgb((chosen.red(), chosen.green(), chosen.blue()))
