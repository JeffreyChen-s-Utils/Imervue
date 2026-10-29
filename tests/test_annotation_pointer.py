"""Qt-delivered pointer events preserve drawing, selection, crop and undo."""
import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QUndoStack

from Imervue.gui.annotation_canvas import AnnotationCanvas
from Imervue.gui.annotation_models import Annotation


@pytest.fixture
def canvas(qapp):
    widget = AnnotationCanvas(Image.new("RGBA", (200, 100)), QUndoStack())
    widget.resize(400, 300)
    yield widget
    widget.close()
    widget.deleteLater()


def pointer(canvas, event_type, point):
    position = canvas._image_to_screen(*point)
    moving = event_type == QEvent.Type.MouseMove
    releasing = event_type == QEvent.Type.MouseButtonRelease
    button = Qt.MouseButton.NoButton if moving else Qt.MouseButton.LeftButton
    buttons = Qt.MouseButton.NoButton if releasing else Qt.MouseButton.LeftButton
    event = QMouseEvent(event_type, position, position, button, buttons, Qt.KeyboardModifier.NoModifier)
    QCoreApplication.sendEvent(canvas, event)


def drag(canvas, start, end):
    pointer(canvas, QEvent.Type.MouseButtonPress, start)
    pointer(canvas, QEvent.Type.MouseMove, end)
    pointer(canvas, QEvent.Type.MouseButtonRelease, end)


def test_draw_move_and_resize_are_independent_undoable_gestures(canvas):
    canvas.set_tool("rect")
    drag(canvas, (20, 20), (60, 60))
    annotation, = canvas.get_annotations()
    assert annotation.points == [(20, 20), (60, 60)]
    canvas.set_tool("select")
    drag(canvas, (40, 40), (50, 45))
    assert annotation.points == [(30, 25), (70, 65)]
    drag(canvas, (30, 25), (15, 10))
    assert annotation.points == [(15, 10), (70, 65)]
    assert canvas._undo_stack.count() == 3
    canvas._undo_stack.undo()
    assert annotation.points == [(30, 25), (70, 65)]
    canvas._undo_stack.undo()
    assert annotation.points == [(20, 20), (60, 60)]
    canvas._undo_stack.undo()
    assert canvas.get_annotations() == []
    canvas._undo_stack.redo()
    canvas._undo_stack.redo()
    canvas._undo_stack.redo()
    assert canvas.get_annotations()[0].points == [(15, 10), (70, 65)]


def test_freehand_keeps_each_move_and_rejects_a_click_without_movement(canvas):
    canvas.set_tool("freehand")
    pointer(canvas, QEvent.Type.MouseButtonPress, (10, 10))
    pointer(canvas, QEvent.Type.MouseMove, (20, 20))
    pointer(canvas, QEvent.Type.MouseMove, (30, 15))
    pointer(canvas, QEvent.Type.MouseButtonRelease, (30, 15))
    annotation, = canvas.get_annotations()
    assert annotation.points == [(10, 10), (20, 20), (30, 15)]
    pointer(canvas, QEvent.Type.MouseButtonPress, (40, 40))
    pointer(canvas, QEvent.Type.MouseButtonRelease, (40, 40))
    assert canvas.get_annotations() == [annotation]
    assert canvas._undo_stack.count() == 1


def test_crop_pointer_routing_does_not_create_an_annotation(canvas):
    canvas.set_tool("crop")
    drag(canvas, (20, 10), (80, 50))
    assert canvas.get_crop_rect() == (20, 10, 60, 40)
    assert canvas.get_annotations() == []
    assert canvas._crop_dragging is False


def test_text_commit_is_reentrant_and_keyboard_shortcuts_reach_the_canvas(canvas):
    canvas.set_tool("text")
    pointer(canvas, QEvent.Type.MouseButtonPress, (20, 20))
    edit = canvas._text_edit
    edit.setText("Caption")
    edit.returnPressed.emit()
    edit.editingFinished.emit()
    annotation, = canvas.get_annotations()
    assert annotation.text == "Caption"
    assert annotation.points == [(20, 20)]
    assert canvas._text_edit is None
    saved = []
    canvas.save_requested.connect(lambda: saved.append(True))
    key = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    QCoreApplication.sendEvent(canvas, key)
    assert saved == [True]


@pytest.mark.parametrize("kind", ["line", "arrow", "freehand"])
@pytest.mark.parametrize("points", [[], [(20, 20)]])
def test_degenerate_paths_cannot_be_selected(canvas, kind, points):
    annotation = Annotation(kind=kind, points=points)
    canvas.set_annotations([annotation])
    assert canvas._hit_annotation(canvas._image_to_screen(20, 20)) is None


def test_lines_use_endpoints_while_freehand_uses_the_entire_path(canvas):
    points = [(10, 10), (50, 80), (90, 10)]
    line = Annotation(kind="line", points=points)
    freehand = Annotation(kind="freehand", points=points)
    canvas.set_annotations([line])
    middle = canvas._image_to_screen(50, 80)
    assert canvas._hit_annotation(middle) is None
    canvas.set_annotations([freehand])
    assert canvas._hit_annotation(middle) is freehand
