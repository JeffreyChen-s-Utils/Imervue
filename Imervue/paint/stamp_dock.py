"""Comic stamp library dock.

Surfaces the catalog in :mod:`Imervue.paint.comic_stamps` as a grid
of clickable thumbnails. Selecting a stamp emits ``stamp_chosen``
with the stamp's i18n key; the workspace renders the stamp into a
new layer at canvas centre.

Thumbnails are pre-rendered once at construction with the same
generator the production insert uses, so the user sees exactly the
shape they will get on click. Pre-render cost is small (~6 raster
shapes at 64×64) and amortised across the dock's lifetime.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QGridLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.comic_stamps import STAMP_LIBRARY, Stamp, render_stamp

THUMB_PX = 64
GRID_COLUMNS = 3


class StampDock(QDockWidget):
    """Click a thumbnail → ``stamp_chosen.emit(stamp_key)``."""

    stamp_chosen = Signal(str)

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_stamps", "Stamps"), parent)
        body = QWidget()
        layout = QVBoxLayout(body)

        grid_widget = QWidget()
        self._grid = QGridLayout(grid_widget)
        self._grid.setSpacing(4)
        layout.addWidget(grid_widget)
        layout.addStretch(1)

        for i, stamp in enumerate(STAMP_LIBRARY):
            btn = self._make_button(stamp)
            self._grid.addWidget(btn, i // GRID_COLUMNS, i % GRID_COLUMNS)

        self.setWidget(body)

    def _make_button(self, stamp: Stamp) -> QToolButton:
        btn = QToolButton()
        btn.setIconSize(btn.iconSize().expandedTo(_qsize(THUMB_PX)))
        btn.setIcon(_thumbnail_icon(stamp))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        lang = language_wrapper.language_word_dict
        btn.setText(lang.get(stamp.key, stamp.fallback_name))
        btn.setAutoRaise(True)
        btn.clicked.connect(
            lambda _checked=False, key=stamp.key: self.stamp_chosen.emit(key),
        )
        return btn


def _qsize(px: int):
    """Tiny shim — avoids importing QSize at module level when this
    file is used as the dock-only side of the import graph."""
    from PySide6.QtCore import QSize
    return QSize(px, px)


def _thumbnail_icon(stamp: Stamp) -> QIcon:
    """Render the stamp at ``THUMB_PX`` and wrap as a QIcon."""
    arr = render_stamp(stamp.key, THUMB_PX, THUMB_PX)
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QIcon(QPixmap.fromImage(img.copy()))
