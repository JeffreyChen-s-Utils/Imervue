"""Tool styles affect only selected annotations of the relevant kind."""
from dataclasses import replace

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack

from Imervue.gui.annotation_canvas import AnnotationCanvas
from Imervue.gui.annotation_models import Annotation


@pytest.fixture
def canvas(qapp):
    widget = AnnotationCanvas(Image.new("RGBA", (20, 20)), QUndoStack())
    yield widget
    widget.close()
    widget.deleteLater()


STYLES = [
    ("set_color", "color", (1, 2, 3, 4), None),
    ("set_stroke_width", "stroke_width", 8, None),
    ("set_brush_type", "brush_type", "marker", "freehand"),
    ("set_brush_opacity", "opacity", 42, "freehand"),
    ("set_brush_spacing", "spacing", 11, "freehand"),
    ("set_font_family", "font_family", "Serif", "text"),
    ("set_font_size", "font_size", 31, "text"),
]


@pytest.mark.parametrize("setter,field,value,required_kind", STYLES)
@pytest.mark.parametrize("kind", ["rect", "freehand", "text"])
def test_styles_update_only_matching_selected_annotations(
    canvas, setter, field, value, required_kind, kind,
):
    selected = Annotation(kind=kind)
    other = Annotation(kind=kind)
    before = replace(selected)
    other_before = replace(other)
    canvas.set_annotations([selected, other])
    canvas._selected_id = selected.id
    emitted = []
    canvas.annotation_changed.connect(lambda: emitted.append(True))

    getattr(canvas, setter)(value)

    expected = value if required_kind in (None, kind) else getattr(before, field)
    assert getattr(selected, field) == expected
    assert other == other_before
    assert canvas._undo_stack.count() == 0
    assert emitted == []


@pytest.mark.parametrize("setter,field,value,required_kind", STYLES)
@pytest.mark.parametrize("selected_id", [None, "deleted-annotation"])
def test_style_defaults_change_without_an_existing_selection(
    canvas, monkeypatch, setter, field, value, required_kind, selected_id,
):
    annotation = Annotation(kind=required_kind or "rect")
    before = replace(annotation)
    canvas.set_annotations([annotation])
    canvas._selected_id = selected_id
    updates = []
    monkeypatch.setattr(canvas, "update", lambda: updates.append(True))

    getattr(canvas, setter)(value)

    defaults = {"opacity": "brush_opacity", "spacing": "brush_spacing"}
    assert getattr(canvas, "_" + defaults.get(field, field)) == value
    assert annotation == before
    assert updates == ([] if selected_id is None else [True])


@pytest.mark.parametrize("setter,field,value,expected", [
    ("set_stroke_width", "stroke_width", 0, 1),
    ("set_stroke_width", "stroke_width", 1, 1),
    ("set_brush_opacity", "opacity", -1, 0),
    ("set_brush_opacity", "opacity", 0, 0),
    ("set_brush_opacity", "opacity", 100, 100),
    ("set_brush_opacity", "opacity", 101, 100),
    ("set_brush_spacing", "spacing", 0, 1),
    ("set_brush_spacing", "spacing", 1, 1),
    ("set_font_size", "font_size", 5, 6),
    ("set_font_size", "font_size", 6, 6),
])
def test_style_bounds_are_applied_to_the_selected_annotation(canvas, setter, field, value, expected):
    annotation = Annotation(kind="text" if field == "font_size" else "freehand")
    canvas.set_annotations([annotation])
    canvas._selected_id = annotation.id
    getattr(canvas, setter)(value)
    assert getattr(annotation, field) == expected


def test_unknown_brush_preserves_default_selection_and_repaint_state(canvas, monkeypatch):
    annotation = Annotation(kind="freehand")
    canvas.set_annotations([annotation])
    canvas._selected_id = annotation.id
    updates = []
    monkeypatch.setattr(canvas, "update", lambda: updates.append(True))
    canvas.set_brush_type("unknown")
    assert canvas.current_brush_type() == "pen"
    assert annotation.brush_type == "pen"
    assert updates == []


def test_all_duplicate_selected_ids_keep_the_same_style(canvas):
    first = Annotation(kind="text")
    second = replace(first)
    canvas.set_annotations([first, second])
    canvas._selected_id = first.id
    canvas.set_stroke_width(w=9)
    assert [annotation.stroke_width for annotation in canvas.get_annotations()] == [9, 9]


@pytest.mark.parametrize("shift", [False, True])
def test_save_shortcut_accepts_both_shift_states_and_unknown_keys_are_unhandled(canvas, shift):
    saved = []
    canvas.save_requested.connect(lambda: saved.append(True))
    assert canvas._handle_ctrl_key(Qt.Key.Key_S, shift) is True
    assert canvas._handle_ctrl_key(Qt.Key.Key_A, shift) is False
    assert saved == [True]
