"""Undo commands for annotation insertion, deletion, and point edits."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

from Imervue.gui.annotation_models import Annotation

if TYPE_CHECKING:
    from Imervue.gui.annotation_canvas import AnnotationCanvas


class _AddAnnotationCommand(QUndoCommand):
    def __init__(self, canvas: AnnotationCanvas, annotation: Annotation):
        super().__init__("Add annotation")
        self._canvas = canvas
        self._ann = annotation

    def redo(self):
        self._canvas._annotations.append(self._ann)
        self._canvas._selected_id = self._ann.id
        self._canvas.update()

    def undo(self):
        self._canvas._annotations = [
            a for a in self._canvas._annotations if a.id != self._ann.id
        ]
        if self._canvas._selected_id == self._ann.id:
            self._canvas._selected_id = None
        self._canvas.update()



class _DeleteAnnotationCommand(QUndoCommand):
    def __init__(self, canvas: AnnotationCanvas, annotation: Annotation):
        super().__init__("Delete annotation")
        self._canvas = canvas
        self._ann = annotation
        self._index = -1

    def redo(self):
        self._index = next(
            (i for i, a in enumerate(self._canvas._annotations) if a.id == self._ann.id),
            -1,
        )
        if self._index >= 0:
            self._canvas._annotations.pop(self._index)
        if self._canvas._selected_id == self._ann.id:
            self._canvas._selected_id = None
        self._canvas.update()

    def undo(self):
        if self._index < 0:
            self._canvas._annotations.append(self._ann)
        else:
            self._canvas._annotations.insert(self._index, self._ann)
        self._canvas.update()



class _ModifyAnnotationCommand(QUndoCommand):
    def __init__(
        self,
        canvas: AnnotationCanvas,
        annotation_id: str,
        old_points: list[tuple[int, int]],
        new_points: list[tuple[int, int]],
    ):
        super().__init__("Move/resize annotation")
        self._canvas = canvas
        self._id = annotation_id
        self._old = list(map(tuple, old_points))
        self._new = list(map(tuple, new_points))

    def _set(self, pts: list[tuple[int, int]]) -> None:
        annotation = self._canvas._find(self._id)
        if annotation is not None:
            annotation.points = list(map(tuple, pts))
        self._canvas.update()

    def redo(self):
        self._set(self._new)

    def undo(self):
        self._set(self._old)
