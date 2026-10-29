"""Annotation styling shared by the current tool and matching selections."""
from __future__ import annotations

from Imervue.gui.annotation_models import ALL_BRUSHES, KIND_FREEHAND, KIND_TEXT


class AnnotationStyleMixin:
    """Apply tool defaults and selected-annotation styles through one policy."""

    def _set_selected_style(self, name: str, value: object, *, kind: str | None = None) -> None:
        if self._selected_id is None:
            return
        for annotation in self._annotations:
            if annotation.id == self._selected_id and (kind is None or annotation.kind == kind):
                setattr(annotation, name, value)
        self.update()

    def set_color(self, color: tuple[int, int, int, int]) -> None:
        self._color = color
        self._set_selected_style("color", color)

    def set_stroke_width(self, w: int) -> None:
        self._stroke_width = max(1, w)
        self._set_selected_style("stroke_width", self._stroke_width)

    def set_brush_type(self, brush: str) -> None:
        if brush not in ALL_BRUSHES:
            return
        self._brush_type = brush
        self._set_selected_style("brush_type", brush, kind=KIND_FREEHAND)

    def set_brush_opacity(self, opacity: int) -> None:
        self._brush_opacity = max(0, min(100, int(opacity)))
        self._set_selected_style("opacity", self._brush_opacity, kind=KIND_FREEHAND)

    def set_brush_spacing(self, spacing: int) -> None:
        self._brush_spacing = max(1, int(spacing))
        self._set_selected_style("spacing", self._brush_spacing, kind=KIND_FREEHAND)

    def set_font_family(self, family: str) -> None:
        self._font_family = family
        self._set_selected_style("font_family", family, kind=KIND_TEXT)

    def set_font_size(self, size: int) -> None:
        self._font_size = max(6, size)
        self._set_selected_style("font_size", self._font_size, kind=KIND_TEXT)
