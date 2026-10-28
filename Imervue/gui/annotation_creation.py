"""Shape/freehand creation and commit, including destructive-effect confirmation."""
from __future__ import annotations

from Imervue.gui.annotation_models import (
    Annotation, AnnotationKind, KIND_FREEHAND, KIND_MOSAIC, KIND_BLUR,
)
from Imervue.gui.annotation_commands import _AddAnnotationCommand


class AnnotationCreationMixin:
    """Shape/freehand creation and commit, including destructive-effect confirmation."""

    def _begin_shape(self, ix: int, iy: int) -> None:
        kind: AnnotationKind = self._tool  # type: ignore[assignment]
        if kind == "freehand":
            self._drawing = Annotation(
                kind=KIND_FREEHAND,
                points=[(ix, iy)],
                color=self._color,
                stroke_width=self._stroke_width,
                brush_type=self._brush_type,  # type: ignore[arg-type]
                opacity=self._brush_opacity,
                spacing=self._brush_spacing,
            )
        else:
            self._drawing = Annotation(
                kind=kind,
                points=[(ix, iy), (ix, iy)],
                color=self._color,
                stroke_width=self._stroke_width,
            )
        self.update()


    def _is_degenerate(self, drawing: Annotation) -> bool:
        if drawing.kind == KIND_FREEHAND:
            return len(drawing.points) < 2
        x1, y1 = drawing.points[0]
        x2, y2 = drawing.points[-1]
        return abs(x2 - x1) < 2 and abs(y2 - y1) < 2


    def _finish_drawing(self) -> None:
        drawing = self._drawing
        self._drawing = None
        if self._is_degenerate(drawing):
            self.update()
            return
        # 馬賽克/模糊：框選完立刻問使用者要多強，確認後把像素烤進 base
        # image（不存檔）。取消就什麼事也不做。
        if drawing.kind in (KIND_MOSAIC, KIND_BLUR):
            if self._prompt_destructive_strength(drawing):
                self.annotation_changed.emit()
            else:
                self.update()
            return
        cmd = _AddAnnotationCommand(self, drawing)
        self._undo_stack.push(cmd)
        self.annotation_changed.emit()
