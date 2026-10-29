"""
比對對話框的 A|B 分割檢視
Compare dialog A|B split view: image A left of a draggable divider, image B right of it.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from Imervue.gui.shown_qimage import shown_qimage


class _SplitLabel(QWidget):
    """A/B split viewer: left half is image A, right half is image B.

    The vertical divider is draggable — click or drag anywhere on the widget
    to move it. Both images are rendered scaled-to-fit using A's aspect
    ratio so the two halves always align on the same pixel grid.
    """

    split_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self._pm_a: QPixmap | None = None
        self._pm_b: QPixmap | None = None
        self._split: float = 0.5
        self._dragging = False
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setMinimumSize(200, 200)
        self.setAutoFillBackground(True)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setMouseTracking(True)

    # --- Public API ---
    def set_pair(self, a_path: str, b_path: str) -> None:
        self._pm_a = QPixmap.fromImage(shown_qimage(a_path))
        self._pm_b = QPixmap.fromImage(shown_qimage(b_path))
        self.update()

    def set_split(self, fraction: float) -> None:
        new_value = max(0.0, min(1.0, float(fraction)))
        if new_value == self._split:
            return
        self._split = new_value
        self.update()
        self.split_changed.emit(new_value)

    def split(self) -> float:
        return self._split

    # --- Paint ---
    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(26, 26, 26))
        if self._pm_a is None or self._pm_b is None:
            return
        if self._pm_a.isNull() or self._pm_b.isNull():
            return

        scaled_a = self._pm_a.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled_b = self._pm_b.scaled(
            scaled_a.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x_off = (self.width() - scaled_a.width()) // 2
        y_off = (self.height() - scaled_a.height()) // 2
        split_x = int(self.width() * self._split)

        painter.setClipRect(0, 0, split_x, self.height())
        painter.drawPixmap(x_off, y_off, scaled_a)
        painter.setClipRect(split_x, 0, self.width() - split_x, self.height())
        painter.drawPixmap(x_off, y_off, scaled_b)
        painter.setClipping(False)
        _draw_split_handle(painter, split_x, self.height())

    # --- Mouse ---
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._set_from_event(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._set_from_event(event)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_from_event(self, event: QMouseEvent) -> None:
        self.set_split(event.position().x() / max(1, self.width()))


def _draw_split_handle(painter: QPainter, split_x: int, height: int) -> None:
    """Paint the divider line plus a pill-shaped grab handle at its midpoint."""
    painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
    painter.drawLine(split_x, 0, split_x, height)
    painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
    painter.setBrush(QColor(255, 255, 255, 220))
    cy = height / 2.0
    painter.drawEllipse(QPointF(split_x, cy), 10.0, 10.0)
