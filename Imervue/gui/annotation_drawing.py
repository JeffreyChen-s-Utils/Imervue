"""QPainter drawing of the annotation canvas.

Every annotation kind (rectangle, ellipse, line, arrow, text, freehand with
its pen / marker / pencil / highlighter / spray / calligraphy / watercolour /
charcoal / crayon brushes, mosaic and blur previews), the selection handles
and the crop overlay (dimming, border, rule-of-thirds guides, handles, size
label). ``AnnotationCanvas.paintEvent`` drives it; ``AnnotationCanvas`` mixes
these methods in.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

from Imervue.gui.annotation_models import (
    KIND_ARROW,
    KIND_BLUR,
    KIND_FREEHAND,
    KIND_LINE,
    KIND_MOSAIC,
    KIND_TEXT,
    Annotation,
    jitter_seed,
)


HANDLE_SIZE = 8  # pixels (screen space)


def _apply_alpha(rgba: tuple[int, int, int, int], multiplier: float) -> QColor:
    r, g, b, a = rgba
    return QColor(r, g, b, int(a * multiplier))


def _draw_simple_path(painter: QPainter, points: list[tuple[float, float]]) -> None:
    path = QPainterPath()
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    painter.drawPath(path)


class AnnotationDrawingMixin:
    """QPainter drawing methods of the annotation canvas."""

    def _paint_crop_overlay(self, painter: QPainter, rect: QRectF) -> None:
        cx, cy, cw, ch = self._crop_rect
        tl = self._image_to_screen(cx, cy)
        br = self._image_to_screen(cx + cw, cy + ch)
        crop_screen = QRectF(tl, br).normalized()
        self._paint_crop_dimming(painter, rect, crop_screen)
        self._paint_crop_border(painter, crop_screen)
        self._paint_crop_thirds(painter, crop_screen)
        self._paint_crop_handles(painter, crop_screen)
        self._paint_crop_size_label(painter, crop_screen, cw, ch)

    @staticmethod
    def _paint_crop_dimming(painter: QPainter, rect: QRectF, crop_screen: QRectF) -> None:
        dim = QColor(0, 0, 0, 140)
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(),
                                crop_screen.top() - rect.top()), dim)
        painter.fillRect(QRectF(rect.left(), crop_screen.bottom(),
                                rect.width(), rect.bottom() - crop_screen.bottom()), dim)
        painter.fillRect(QRectF(rect.left(), crop_screen.top(),
                                crop_screen.left() - rect.left(),
                                crop_screen.height()), dim)
        painter.fillRect(QRectF(crop_screen.right(), crop_screen.top(),
                                rect.right() - crop_screen.right(),
                                crop_screen.height()), dim)

    @staticmethod
    def _paint_crop_border(painter: QPainter, crop_screen: QRectF) -> None:
        crop_pen = QPen(QColor(255, 255, 255))
        crop_pen.setWidthF(1.5)
        crop_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(crop_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(crop_screen)

    @staticmethod
    def _paint_crop_thirds(painter: QPainter, crop_screen: QRectF) -> None:
        thirds_pen = QPen(QColor(255, 255, 255, 80))
        thirds_pen.setWidthF(0.5)
        painter.setPen(thirds_pen)
        for i in range(1, 3):
            tx = crop_screen.left() + crop_screen.width() * i / 3
            ty = crop_screen.top() + crop_screen.height() * i / 3
            painter.drawLine(QPointF(tx, crop_screen.top()),
                             QPointF(tx, crop_screen.bottom()))
            painter.drawLine(QPointF(crop_screen.left(), ty),
                             QPointF(crop_screen.right(), ty))

    def _paint_crop_handles(self, painter: QPainter, crop_screen: QRectF) -> None:
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 120, 215), 1))
        h = HANDLE_SIZE
        for hx, hy in self._handle_positions(crop_screen):
            painter.drawRect(QRectF(hx - h / 2, hy - h / 2, h, h))

    @staticmethod
    def _paint_crop_size_label(painter: QPainter, crop_screen: QRectF,
                               cw: int, ch: int) -> None:
        painter.setPen(QPen(QColor(255, 255, 255)))
        label_font = QFont()
        label_font.setPixelSize(12)
        painter.setFont(label_font)
        painter.drawText(
            QPointF(crop_screen.left() + 4, crop_screen.top() - 4),
            f"{cw} x {ch}")

    def _draw_annotation_qt(self, painter: QPainter, ann: Annotation) -> None:
        color = QColor(*ann.color)
        self._prepare_annotation_pen(painter, ann, color)
        dispatch = {
            "rect": self._draw_rect_qt,
            "ellipse": self._draw_ellipse_qt,
            KIND_LINE: self._draw_line_qt,
            KIND_ARROW: self._draw_arrow_qt,
            KIND_FREEHAND: self._draw_freehand_if_valid,
            KIND_TEXT: self._draw_text_qt,
        }
        handler = dispatch.get(ann.kind)
        if handler is not None:
            handler(painter, ann)
        elif ann.kind in (KIND_MOSAIC, KIND_BLUR):
            self._draw_pixel_effect_preview(painter, ann, color)

    @staticmethod
    def _prepare_annotation_pen(painter: QPainter, ann: Annotation, color: QColor) -> None:
        pen = QPen(color)
        pen.setWidthF(ann.stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(color) if ann.filled else Qt.BrushStyle.NoBrush)

    @staticmethod
    def _draw_rect_qt(painter: QPainter, ann: Annotation) -> None:
        x1, y1, x2, y2 = ann.bounding_box()
        painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

    @staticmethod
    def _draw_ellipse_qt(painter: QPainter, ann: Annotation) -> None:
        x1, y1, x2, y2 = ann.bounding_box()
        painter.drawEllipse(QRectF(x1, y1, x2 - x1, y2 - y1))

    @staticmethod
    def _draw_line_qt(painter: QPainter, ann: Annotation) -> None:
        if len(ann.points) >= 2:
            painter.drawLine(QPointF(*ann.points[0]),
                             QPointF(*ann.points[-1]))

    def _draw_freehand_if_valid(self, painter: QPainter, ann: Annotation) -> None:
        if len(ann.points) >= 2:
            self._draw_freehand_qt(painter, ann)

    @staticmethod
    def _draw_text_qt(painter: QPainter, ann: Annotation) -> None:
        if not (ann.text and ann.points):
            return
        font = QFont(ann.font_family) if ann.font_family else QFont()
        font.setPixelSize(max(6, ann.font_size))
        painter.setFont(font)
        painter.setPen(QPen(QColor(*ann.color)))
        painter.drawText(QPointF(*ann.points[0]), ann.text)

    @staticmethod
    def _draw_pixel_effect_preview(painter: QPainter, ann: Annotation, color: QColor) -> None:
        preview_pen = QPen(color)
        preview_pen.setWidthF(2)
        preview_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(preview_pen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
        x1, y1, x2, y2 = ann.bounding_box()
        region = QRectF(x1, y1, x2 - x1, y2 - y1)
        painter.drawRect(region)
        label_font = QFont()
        label_font.setPixelSize(max(12, int(min(region.width(), region.height()) / 8)))
        painter.setFont(label_font)
        painter.drawText(region, Qt.AlignmentFlag.AlignCenter, ann.kind)

    def _draw_arrow_qt(self, painter: QPainter, ann: Annotation) -> None:
        if len(ann.points) < 2:
            return
        sx, sy = ann.points[0]
        ex, ey = ann.points[-1]
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length < 1:
            return
        head_len = max(10, ann.stroke_width * 5)
        head_half = max(6, ann.stroke_width * 3)
        ux, uy = dx / length, dy / length
        line_end = QPointF(ex - ux * head_len * 0.6, ey - uy * head_len * 0.6)
        painter.drawLine(QPointF(sx, sy), line_end)
        base_center = (ex - ux * head_len, ey - uy * head_len)
        px, py = -uy, ux
        poly = QPolygonF([
            QPointF(ex, ey),
            QPointF(base_center[0] + px * head_half, base_center[1] + py * head_half),
            QPointF(base_center[0] - px * head_half, base_center[1] - py * head_half),
        ])
        painter.setBrush(QBrush(QColor(*ann.color)))
        painter.drawPolygon(poly)

    def _draw_freehand_qt(self, painter: QPainter, ann: Annotation) -> None:
        """Live-preview counterpart to PIL ``_draw_freehand`` — mirrors the
        brush styles so what the user sees while dragging matches what
        ``bake()`` will produce on save.
        """
        brush = getattr(ann, "brush_type", "pen")
        opacity = max(0, min(100, int(getattr(ann, "opacity", 100))))
        if self._dispatch_dedicated_brush(painter, ann, brush, opacity):
            return

        alpha_scale, width_factor = self._BRUSH_PRESETS.get(
            brush, self._BRUSH_PRESETS["pen"]
        )
        width = max(1, int(ann.stroke_width * width_factor))
        color = _apply_alpha(ann.color, alpha_scale * opacity / 100)
        self._apply_simple_brush_pen(painter, color, width)

        if brush == "watercolor":
            self._draw_watercolor_qt(painter, ann, width)
        elif brush == "crayon":
            self._draw_crayon_qt(painter, ann, color, width)
        else:
            _draw_simple_path(painter, ann.points)

    def _dispatch_dedicated_brush(
        self, painter: QPainter, ann: Annotation, brush: str, opacity: int
    ) -> bool:
        if brush == "spray":
            self._draw_freehand_spray_qt(painter, ann, opacity)
            return True
        if brush == "calligraphy":
            self._draw_freehand_calligraphy_qt(painter, ann, opacity)
            return True
        if brush == "charcoal":
            self._draw_freehand_charcoal_qt(painter, ann, opacity)
            return True
        return False

    @staticmethod
    def _apply_simple_brush_pen(painter: QPainter, color: QColor, width: int) -> None:
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    @staticmethod
    def _draw_watercolor_qt(painter: QPainter, ann: Annotation, width: int) -> None:
        import random as _random
        rng = _random.Random(jitter_seed(ann.id))  # nosec B311  # NOSONAR S2245
        jitter = width * 0.15
        for _ in range(3):
            path = QPainterPath()
            pts = ann.points
            path.moveTo(pts[0][0] + rng.gauss(0, jitter),
                        pts[0][1] + rng.gauss(0, jitter))
            for px, py in pts[1:]:
                path.lineTo(px + rng.gauss(0, jitter),
                            py + rng.gauss(0, jitter))
            painter.drawPath(path)

    @staticmethod
    def _draw_crayon_qt(painter: QPainter, ann: Annotation,
                        color: QColor, width: int) -> None:
        import random as _random
        rng = _random.Random(jitter_seed(ann.id))  # nosec B311  # NOSONAR S2245
        for offset in range(3):
            w = max(1, width - offset)
            pen2 = QPen(color)
            pen2.setWidthF(w)
            pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen2)
            path = QPainterPath()
            pts = ann.points
            path.moveTo(pts[0][0] + rng.uniform(-1, 1),
                        pts[0][1] + rng.uniform(-1, 1))
            for px, py in pts[1:]:
                path.lineTo(px + rng.uniform(-1, 1),
                            py + rng.uniform(-1, 1))
            painter.drawPath(path)

    def _draw_freehand_spray_qt(
        self, painter: QPainter, ann: Annotation, opacity: int
    ) -> None:
        import random as _random
        r, g, b, a = ann.color
        final_alpha = int(a * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        radius = max(1, ann.stroke_width)
        spread = max(2, ann.stroke_width * 3)
        spacing = max(1, int(ann.spacing))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))

        rng = _random.Random(jitter_seed(ann.id))  # nosec B311  # NOSONAR S2245
        pts = ann.points
        samples: list[tuple[float, float]] = [
            (float(pts[0][0]), float(pts[0][1]))
        ]
        accumulated = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len <= 0:
                continue
            ux, uy = (x2 - x1) / seg_len, (y2 - y1) / seg_len
            remaining = seg_len
            while accumulated + remaining >= spacing:
                step = spacing - accumulated
                cx = x1 + ux * (seg_len - remaining + step)
                cy = y1 + uy * (seg_len - remaining + step)
                samples.append((cx, cy))
                remaining -= step
                accumulated = 0.0
            accumulated += remaining

        dots_per_sample = max(4, ann.stroke_width * 2)
        for cx, cy in samples:
            for _ in range(dots_per_sample):
                while True:
                    ox = rng.uniform(-spread, spread)
                    oy = rng.uniform(-spread, spread)
                    if ox * ox + oy * oy <= spread * spread:
                        break
                painter.drawEllipse(
                    QRectF(cx + ox - radius / 2, cy + oy - radius / 2,
                           radius, radius)
                )

    def _draw_freehand_calligraphy_qt(
        self, painter: QPainter, ann: Annotation, opacity: int
    ) -> None:
        """Calligraphy: variable width based on stroke direction."""
        r, g, b, a = ann.color
        final_alpha = int(a * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        base_w = max(1, ann.stroke_width)
        nib_angle = math.pi / 4
        cos_a, sin_a = math.cos(nib_angle), math.sin(nib_angle)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pts = ann.points
        for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
            dx, dy = x2 - x1, y2 - y1
            seg_len = math.hypot(dx, dy)
            if seg_len < 0.5:
                continue
            ux, uy = dx / seg_len, dy / seg_len
            proj = abs(ux * cos_a + uy * sin_a)
            w = max(1, int(base_w * (0.3 + 0.7 * proj)))
            pen = QPen(color)
            pen.setWidthF(w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_freehand_charcoal_qt(
        self, painter: QPainter, ann: Annotation, opacity: int
    ) -> None:
        """Charcoal: rough textured stroke with scattered dots."""
        import random as _random
        r, g, b, a = ann.color
        final_alpha = int(a * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        width = max(1, int(ann.stroke_width * 1.2))
        rng = _random.Random(jitter_seed(ann.id))  # nosec B311  # NOSONAR S2245
        # Main stroke
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(*ann.points[0])
        for p in ann.points[1:]:
            path.lineTo(*p)
        painter.drawPath(path)
        # Scatter texture dots
        spread = max(2, width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        for x, y in ann.points[::3]:
            for _ in range(2):
                ox = rng.gauss(0, spread * 0.5)
                oy = rng.gauss(0, spread * 0.5)
                r2 = max(0.5, width * 0.3)
                painter.drawEllipse(QRectF(x + ox - r2, y + oy - r2, r2 * 2, r2 * 2))

    def _draw_selection(self, painter: QPainter, ann: Annotation) -> None:
        if ann.kind == KIND_TEXT:
            x1, y1, x2, y2 = self._text_bounding_box(ann)
        else:
            x1, y1, x2, y2 = ann.bounding_box()
        top_left = self._image_to_screen(x1, y1)
        bottom_right = self._image_to_screen(x2, y2)
        sel_rect = QRectF(top_left, bottom_right)

        pen = QPen(QColor(0, 150, 255))
        pen.setWidthF(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sel_rect)

        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 150, 255), 1))
        h = HANDLE_SIZE
        for hx, hy in self._handle_positions(sel_rect):
            painter.drawRect(QRectF(hx - h / 2, hy - h / 2, h, h))
