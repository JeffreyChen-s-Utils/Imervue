"""Delete-key behaviour on the Modify tab's AnnotationCanvas.

With an annotation selected, Delete removes it (existing behaviour). With
nothing selected, Delete must request deletion of the *image* — the Modify tab
wires this to trash the current image, since the viewer is hidden there and
can't receive the key. Backspace is deliberately not wired to image deletion.
"""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QUndoStack

from Imervue.gui.annotation_canvas import AnnotationCanvas


def _canvas():
    return AnnotationCanvas(Image.new("RGBA", (16, 16)), QUndoStack())


def _press(canvas, key):
    canvas.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def test_delete_with_no_selection_requests_image_delete(qapp):
    canvas = _canvas()
    try:
        requested: list[bool] = []
        canvas.delete_image_requested.connect(lambda: requested.append(True))
        canvas._selected_id = None                 # nothing selected
        _press(canvas, Qt.Key.Key_Delete)
        assert requested == [True]
    finally:
        canvas.deleteLater()


def test_backspace_with_no_selection_does_not_delete_image(qapp):
    canvas = _canvas()
    try:
        requested: list[bool] = []
        canvas.delete_image_requested.connect(lambda: requested.append(True))
        canvas._selected_id = None
        _press(canvas, Qt.Key.Key_Backspace)       # Backspace is left alone
        assert requested == []
    finally:
        canvas.deleteLater()


def test_delete_with_a_selection_does_not_delete_image(qapp):
    canvas = _canvas()
    try:
        requested: list[bool] = []
        canvas.delete_image_requested.connect(lambda: requested.append(True))
        canvas._selected_id = "some-annotation-id"  # a selection exists
        _press(canvas, Qt.Key.Key_Delete)
        assert requested == []                      # acts on the annotation, not the image
    finally:
        canvas.deleteLater()
