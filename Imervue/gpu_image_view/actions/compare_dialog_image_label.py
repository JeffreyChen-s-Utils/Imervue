"""
比對對話框的單張檢視
Compare dialog image view: a fitted, zoomable, pannable label whose view state
the side-by-side grid keeps in sync across tiles.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from Imervue.gui.shown_qimage import shown_qimage


class _ImageLabel(QLabel):
    """QLabel that keeps a source QPixmap and re-scales on resize."""

    view_changed = Signal(float, float, float)

    def __init__(self, path: str | None = None):
        super().__init__()
        self._pixmap: QPixmap | None = None
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._drag_pos: QPointF | None = None
        self._syncing = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        self.setMouseTracking(True)
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        self._pixmap = QPixmap.fromImage(shown_qimage(path))
        self.reset_view()
        self.update()

    def set_qimage(self, qimg: QImage) -> None:
        self._pixmap = QPixmap.fromImage(qimg)
        self.reset_view()
        self.update()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

    def sync_view(self, zoom: float, pan_x: float, pan_y: float) -> None:
        self._syncing = True
        try:
            self._zoom = zoom
            self._pan_x = pan_x
            self._pan_y = pan_y
            self.update()
        finally:
            self._syncing = False

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        if self._pixmap is None or self._pixmap.isNull():
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            scaled = self._pixmap.scaled(
                QSize(
                    max(1, int(self.width() * self._zoom)),
                    max(1, int(self.height() * self._zoom)),
                ),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) / 2 + self._pan_x
            y = (self.height() - scaled.height()) / 2 + self._pan_y
            painter.drawPixmap(int(x), int(y), scaled)
        finally:
            painter.end()

    def wheelEvent(self, event):  # noqa: N802
        old = self._zoom
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom = max(1.0, min(12.0, self._zoom * factor))
        if self._zoom != old:
            self._emit_view_changed()
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_pos is not None:
            delta = event.position() - self._drag_pos
            self._drag_pos = event.position()
            self._pan_x += delta.x()
            self._pan_y += delta.y()
            self._emit_view_changed()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _emit_view_changed(self) -> None:
        if not self._syncing:
            self.view_changed.emit(self._zoom, self._pan_x, self._pan_y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()
