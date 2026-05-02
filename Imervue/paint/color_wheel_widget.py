"""QWidget rendering the hue-ring + SV-triangle picker.

Uses the pure-math helpers from :mod:`Imervue.paint.color_wheel`
for hit testing + colour conversions. Draws the ring as a sequence
of pie-slice gradients and the triangle as a filled polygon
modulated by SV; emits :attr:`color_chosen` whenever the user
picks a new colour via either region.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from Imervue.paint.color_wheel import (
    DEFAULT_RING_INNER,
    DEFAULT_RING_OUTER,
    REGION_RING,
    REGION_TRIANGLE,
    classify_region,
    hsv_to_rgb,
    ring_angle_to_hue,
    rgb_to_hsv,
    sv_to_triangle,
    triangle_to_sv,
    triangle_vertices,
)

_DEFAULT_SIZE = 200


class ColorWheelWidget(QWidget):
    """Hue-ring + SV-triangle colour picker."""

    color_chosen = Signal(int, int, int)   # (r, g, b)

    def __init__(
        self,
        initial_rgb: tuple[int, int, int] = (255, 0, 0),
        parent=None,
    ):
        super().__init__(parent)
        self.setMinimumSize(_DEFAULT_SIZE, _DEFAULT_SIZE)
        self._dragging_region: str | None = None
        h, s, v = rgb_to_hsv(*initial_rgb)
        self._hue = float(h)
        self._saturation = float(s)
        self._value = float(v)

    # ---- public --------------------------------------------------------

    def set_color(self, rgb: tuple[int, int, int]) -> None:
        """Update the picker's selected colour without emitting."""
        h, s, v = rgb_to_hsv(*rgb)
        self._hue = float(h)
        self._saturation = float(s)
        self._value = float(v)
        self.update()

    def color(self) -> tuple[int, int, int]:
        return hsv_to_rgb(self._hue, self._saturation, self._value)

    # ---- coordinate helpers (testable) --------------------------------

    def _to_unit(self, pos: QPointF) -> tuple[float, float]:
        """Convert widget-space ``QPointF`` into the picker's unit space."""
        radius = self._unit_radius()
        if radius <= 0:
            return (0.0, 0.0)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        return ((pos.x() - cx) / radius, (pos.y() - cy) / radius)

    def _from_unit(self, point: tuple[float, float]) -> QPointF:
        radius = self._unit_radius()
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        return QPointF(cx + point[0] * radius, cy + point[1] * radius)

    def _unit_radius(self) -> float:
        return min(self.width(), self.height()) / 2.0 - 4.0

    # ---- mouse routing -------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        unit = self._to_unit(event.position())
        region = classify_region(unit)
        if region == REGION_RING:
            self._dragging_region = REGION_RING
            self._update_hue_from_unit(unit)
        elif region == REGION_TRIANGLE:
            self._dragging_region = REGION_TRIANGLE
            self._update_sv_from_unit(unit)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        if self._dragging_region is None:
            return
        unit = self._to_unit(event.position())
        if self._dragging_region == REGION_RING:
            self._update_hue_from_unit(unit)
        else:
            self._update_sv_from_unit(unit)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pragma: no cover
        self._dragging_region = None

    def _update_hue_from_unit(self, unit: tuple[float, float]) -> None:
        angle = math.atan2(-unit[1], unit[0])   # invert y for screen coords
        self._hue = ring_angle_to_hue(angle)
        self._emit_color()
        self.update()

    def _update_sv_from_unit(self, unit: tuple[float, float]) -> None:
        s, v = triangle_to_sv(unit, self._hue)
        self._saturation = s
        self._value = v
        self._emit_color()
        self.update()

    def _emit_color(self) -> None:
        r, g, b = self.color()
        self.color_chosen.emit(r, g, b)

    # ---- painting ------------------------------------------------------

    def paintEvent(self, event) -> None:  # pragma: no cover - Qt UI
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_ring(painter)
            self._paint_triangle(painter)
            self._paint_indicators(painter)
        finally:
            painter.end()

    def _paint_ring(self, painter: QPainter) -> None:  # pragma: no cover - Qt UI
        radius = self._unit_radius()
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        gradient = QConicalGradient(QPointF(cx, cy), 90.0)
        for stop in range(0, 13):
            t = stop / 12.0
            r, g, b = hsv_to_rgb(t, 1.0, 1.0)
            gradient.setColorAt(t, QColor(r, g, b))
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        outer_rect = QRectF(
            cx - radius * DEFAULT_RING_OUTER,
            cy - radius * DEFAULT_RING_OUTER,
            radius * DEFAULT_RING_OUTER * 2,
            radius * DEFAULT_RING_OUTER * 2,
        )
        painter.drawEllipse(outer_rect)
        # Punch a transparent hole using the inner radius.
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Clear,
        )
        inner_rect = QRectF(
            cx - radius * DEFAULT_RING_INNER,
            cy - radius * DEFAULT_RING_INNER,
            radius * DEFAULT_RING_INNER * 2,
            radius * DEFAULT_RING_INNER * 2,
        )
        painter.drawEllipse(inner_rect)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver,
        )

    def _paint_triangle(self, painter: QPainter) -> None:  # pragma: no cover
        from PySide6.QtGui import QPolygonF
        sat, white, black = triangle_vertices(self._hue)
        sat_qp = self._from_unit(sat)
        white_qp = self._from_unit(white)
        black_qp = self._from_unit(black)
        polygon = QPolygonF([sat_qp, white_qp, black_qp])
        # Cheap fill with the saturated-corner colour; the ring's
        # gradient already does the heavy lifting visually.
        r, g, b = hsv_to_rgb(self._hue, 1.0, 1.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(r, g, b))
        painter.drawPolygon(polygon)

    def _paint_indicators(self, painter: QPainter) -> None:  # pragma: no cover
        # Hue cursor on the ring.
        ring_radius = self._unit_radius() * (
            DEFAULT_RING_INNER + DEFAULT_RING_OUTER
        ) / 2.0
        angle = math.radians(90.0 - self._hue * 360.0)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        ring_pos = QPointF(
            cx + ring_radius * math.cos(angle),
            cy + ring_radius * math.sin(-angle),
        )
        painter.setPen(QColor("#fff"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring_pos, 4.0, 4.0)
        # SV cursor inside the triangle.
        sv = self._from_unit(
            sv_to_triangle(self._saturation, self._value, self._hue),
        )
        painter.drawEllipse(sv, 4.0, 4.0)
