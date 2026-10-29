"""Image/widget coordinates and compositing of annotation canvas layers."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainter

from Imervue.gui.annotation_models import TOOL_CROP
from Imervue.gui.annotation_geometry import fit_display_scale as _fit_display_scale


class AnnotationViewportMixin:
    """Image/widget coordinates and compositing of annotation canvas layers."""

    def _display_rect(self) -> QRectF:
        bw, bh = self._base.width, self._base.height
        cw, ch = self.width(), self.height()
        scale = _fit_display_scale(bw, bh, cw, ch)
        if scale <= 0:
            return QRectF(0, 0, 0, 0)
        dw, dh = bw * scale, bh * scale
        return QRectF((cw - dw) / 2, (ch - dh) / 2, dw, dh)


    def _screen_to_image(self, x: float, y: float) -> tuple[int, int]:
        rect = self._display_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return (0, 0)
        ix = (x - rect.x()) * self._base.width / rect.width()
        iy = (y - rect.y()) * self._base.height / rect.height()
        return (int(round(ix)), int(round(iy)))


    def _image_to_screen(self, ix: float, iy: float) -> QPointF:
        rect = self._display_rect()
        if self._base.width == 0 or self._base.height == 0:
            return QPointF(0, 0)
        sx = rect.x() + ix * rect.width() / self._base.width
        sy = rect.y() + iy * rect.height() / self._base.height
        return QPointF(sx, sy)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        rect = self._display_rect()
        if rect.width() > 0:
            self._paint_image_and_annotations(painter, rect)
        if self._selected_id is not None:
            sel = self._find(self._selected_id)
            if sel is not None:
                self._draw_selection(painter, sel)
        if (self._tool == TOOL_CROP and self._crop_rect is not None
                and rect.width() > 0):
            self._paint_crop_overlay(painter, rect)
        painter.end()


    def _paint_image_and_annotations(self, painter: QPainter, rect: QRectF) -> None:
        painter.drawImage(rect, self._base_qimg)
        painter.save()
        painter.translate(rect.x(), rect.y())
        painter.scale(
            rect.width() / self._base.width,
            rect.height() / self._base.height,
        )
        if (self._preview_qimg is not None
                and self._preview_rect_image is not None):
            px, py, pw, ph = self._preview_rect_image
            painter.drawImage(QRectF(px, py, pw, ph), self._preview_qimg)
        for ann in self._annotations:
            self._draw_annotation_qt(painter, ann)
        if self._drawing is not None:
            self._draw_annotation_qt(painter, self._drawing)
        painter.restore()
