"""Scrollable two-column tool rail, rearranged into two rows when docked horizontally."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QScrollArea, QSizePolicy, QStyle, QToolButton, QWidget,
)

from Imervue.system.ui_scale import scaled_px


class ToolPalette(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("paintToolPalette")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self._body = QWidget()
        self._grid = QGridLayout(self._body)
        self._grid.setContentsMargins(scaled_px(4), scaled_px(4), scaled_px(4), scaled_px(4))
        self._grid.setSpacing(scaled_px(4))
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._items: list[QWidget] = []
        self.setWidget(self._body)
        self._vertical = True

    def add_tool_action(self, action) -> None:
        button = QToolButton(self._body)
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setAccessibleName(action.text())
        button.setProperty("paintTool", True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(scaled_px(21), scaled_px(21)))
        button.setFixedSize(scaled_px(34), scaled_px(34))
        self._items.append(button)

    def add_separator(self) -> None:
        line = QFrame(self._body)
        line.setObjectName("toolGroupSeparator")
        self._items.append(line)

    def set_orientation(self, orientation) -> None:
        self._vertical = orientation == Qt.Orientation.Vertical
        while self._grid.count():
            self._grid.takeAt(0)
        slot = 0
        for item in self._items:
            if isinstance(item, QToolButton):
                slot = self._place_tool(item, slot)
            else:
                slot = self._place_separator(item, slot)
        self._set_scroll_direction()

    def _place_tool(self, item: QToolButton, slot: int) -> int:
        row, column = divmod(slot, 2)
        if not self._vertical:
            row, column = column, row
        self._grid.addWidget(item, row, column)
        return slot + 1

    def _place_separator(self, item: QFrame, slot: int) -> int:
        row = (slot + 1) // 2
        if self._vertical:
            item.setFrameShape(QFrame.Shape.HLine)
            self._grid.addWidget(item, row, 0, 1, 2)
        else:
            item.setFrameShape(QFrame.Shape.VLine)
            self._grid.addWidget(item, 0, row, 2, 1)
        return (row + 1) * 2

    def _set_scroll_direction(self) -> None:
        span = self._cross_extent()
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        if self._vertical:
            self.setFixedWidth(span)
            self.setMinimumHeight(scaled_px(80))
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(span)
            self.setMinimumWidth(scaled_px(80))
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        always_off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        as_needed = Qt.ScrollBarPolicy.ScrollBarAsNeeded
        self.setVerticalScrollBarPolicy(as_needed if self._vertical else always_off)
        self.setHorizontalScrollBarPolicy(always_off if self._vertical else as_needed)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(self._cross_extent(), scaled_px(480)) if self._vertical else QSize(
            scaled_px(480), self._cross_extent())

    def _cross_extent(self) -> int:
        scrollbar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        return max(scaled_px(88), 2 * scaled_px(34) + 3 * scaled_px(4) + scrollbar)
