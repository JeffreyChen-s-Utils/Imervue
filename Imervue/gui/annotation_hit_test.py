"""Topmost annotation and resize-handle picking in image/widget coordinates."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from Imervue.gui.annotation_models import Annotation, KIND_TEXT, KIND_FREEHAND
from Imervue.gui.annotation_drawing import HANDLE_SIZE
from Imervue.gui.annotation_geometry import point_segment_distance as _point_segment_distance


class AnnotationHitTestMixin:
    """Topmost annotation and resize-handle picking in image/widget coordinates."""

    def _hit_handle(self, pt: QPointF) -> str | None:
        if self._selected_id is None:
            return None
        sel = self._find(self._selected_id)
        if sel is None:
            return None
        if sel.kind == KIND_TEXT:
            x1, y1, x2, y2 = self._text_bounding_box(sel)
        else:
            x1, y1, x2, y2 = sel.bounding_box()
        sel_rect = QRectF(
            self._image_to_screen(x1, y1),
            self._image_to_screen(x2, y2),
        )
        h = HANDLE_SIZE
        for name, (hx, hy) in zip(
            self._HANDLE_NAMES, self._handle_positions(sel_rect), strict=False,
        ):
            box = QRectF(hx - h, hy - h, h * 2, h * 2)
            if box.contains(pt):
                return name
        return None


    def _hit_annotation(self, pt: QPointF) -> Annotation | None:
        """Find the topmost annotation under ``pt`` (widget coords).

        Uses bounding-box hit for shape annotations and segment-distance
        hit for line-like annotations — a diagonal line's bounding box can
        be huge, and picking anywhere inside it would make selection feel
        broken.
        """
        ix, iy = self._screen_to_image(pt.x(), pt.y())
        for a in reversed(self._annotations):  # topmost first
            if self._annotation_hits_point(a, ix, iy):
                return a
        return None


    def _annotation_hits_point(self, a: Annotation, ix: int, iy: int) -> bool:
        """Pick paths by segment distance and other annotations by bounds."""
        tol = max(5, a.stroke_width + 2)
        if a.kind in ("line", "arrow", KIND_FREEHAND):
            if len(a.points) < 2:
                return False
            points = a.points if a.kind == KIND_FREEHAND else [a.points[0], a.points[-1]]
            return any(
                _point_segment_distance(ix, iy, p, q) <= tol
                for p, q in zip(points, points[1:], strict=False)
            )
        return self._bbox_annotation_hits(a, ix, iy, tol)

    def _bbox_annotation_hits(
        self, a: Annotation, ix: int, iy: int, tol: float,
    ) -> bool:
        if a.kind == KIND_TEXT:
            x1, y1, x2, y2 = self._text_bounding_box(a)
        else:
            x1, y1, x2, y2 = a.bounding_box()
        return x1 - tol <= ix <= x2 + tol and y1 - tol <= iy <= y2 + tol


    def _find(self, ann_id: str) -> Annotation | None:
        for a in self._annotations:
            if a.id == ann_id:
                return a
        return None

