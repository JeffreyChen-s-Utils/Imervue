"""Saved multi-stop gradients: the stop maths, the editor dialog, the tool and the Options bar.

``paint/gradient_editor.py`` (multi-stop gradients that persist) was built and
tested but unreachable: the gradient tool only painted foreground → background.
Now the gradient Options bar picks a saved gradient or foreground → background,
**Edit…** opens :class:`GradientEditorDialog`, and the tool paints the chosen one.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.gradient import render_gradient
from Imervue.paint.gradient_editor import (
    GradientStop,
    MultiStopGradient,
    add_stop,
    default_gradient,
    load_gradients,
    move_stop,
    recolour_stop,
    remove_stop,
    render_multistop_gradient,
    save_gradients,
)
from Imervue.paint.gradient_editor_dialog import GradientEditorDialog, unique_name
from Imervue.paint.tool_bar import PaintOptionsBar
from Imervue.paint.tools.retouch import GradientTool
from Imervue.user_settings.user_setting_dict import user_setting_dict

_RED, _BLUE, _GREEN = (255, 0, 0, 255), (0, 0, 255, 255), (0, 200, 0, 255)


@pytest.fixture(autouse=True)
def _clean():
    for key in ("paint_state", "paint_multistop_gradients"):
        user_setting_dict.pop(key, None)
    ts.reset_tool_state()
    yield
    for key in ("paint_state", "paint_multistop_gradients"):
        user_setting_dict.pop(key, None)
    ts.reset_tool_state()


def _three_stops(name: str = "sunset") -> MultiStopGradient:
    return MultiStopGradient(name, (GradientStop(0.0, _RED), GradientStop(0.5, _GREEN),
                                    GradientStop(1.0, _BLUE)))


# --- stop maths ----------------------------------------------------------------

def test_a_new_gradient_runs_between_its_two_ends():
    gradient = default_gradient("g", _RED, _BLUE)
    assert [(s.position, s.color) for s in gradient.stops] == [(0.0, _RED), (1.0, _BLUE)]


def test_add_stop_fills_the_widest_gap_with_the_colour_there():
    gradient = MultiStopGradient("g", (GradientStop(0.0, _RED), GradientStop(0.2, _RED),
                                       GradientStop(1.0, _BLUE)))
    added, index = add_stop(gradient)
    assert index == 2
    assert added.stops[2].position == pytest.approx(0.6)
    assert added.stops[2].color == pytest.approx((128, 0, 128, 255), abs=1)
    assert len(gradient.stops) == 3                        # the input is unchanged


def test_remove_stop_keeps_both_ends():
    gradient = _three_stops()
    assert remove_stop(gradient, 0) is gradient
    assert remove_stop(gradient, 2) is gradient
    assert [s.color for s in remove_stop(gradient, 1).stops] == [_RED, _BLUE]


def test_move_stop_stays_between_its_neighbours_and_the_ends_stay_put():
    gradient = _three_stops()
    assert move_stop(gradient, 1, 0.8).stops[1].position == pytest.approx(0.8)
    assert move_stop(gradient, 1, 1.7).stops[1].position == pytest.approx(1.0)
    assert move_stop(gradient, 1, -0.4).stops[1].position == pytest.approx(0.0)
    assert move_stop(gradient, 0, 0.3) is gradient


def test_recolour_stop_changes_only_that_stop():
    recoloured = recolour_stop(_three_stops(), 1, (1, 2, 3, 4))
    assert [s.color for s in recoloured.stops] == [_RED, (1, 2, 3, 4), _BLUE]


def test_repeat_tiles_the_gradient_like_the_two_colour_one():
    two_stop = default_gradient("g", (*(10, 20, 30), 255), (*(200, 100, 50), 255))
    canvas_a = np.zeros((4, 40, 4), np.uint8)
    canvas_b = np.zeros((4, 40, 4), np.uint8)
    render_multistop_gradient(canvas_a, (0, 2), (39, 2), two_stop, repeat=3, reverse=True)
    render_gradient(canvas_b, (0, 2), (39, 2), (10, 20, 30), (200, 100, 50), repeat=3, reverse=True)
    assert np.abs(canvas_a.astype(int) - canvas_b.astype(int)).max() <= 1


def test_unique_name_counts_up():
    assert unique_name("Gradient", set()) == "Gradient"
    assert unique_name("Gradient", {"Gradient", "Gradient 2"}) == "Gradient 3"


# --- the gradient tool ----------------------------------------------------------

def _drag(tool: GradientTool, canvas: np.ndarray) -> bool:
    tool.handle(PointerEvent(phase="press", x=0, y=2, button=1, modifiers=0, pressure=1.0), canvas)
    return tool.handle(PointerEvent(phase="release", x=39, y=2, button=1, modifiers=0,
                                    pressure=1.0), canvas)


def test_the_tool_paints_the_chosen_saved_gradient():
    save_gradients([_three_stops()])
    state = ts.load_tool_state()
    state.set_gradient(name="sunset")
    canvas = np.zeros((4, 40, 4), np.uint8)
    assert _drag(GradientTool(state), canvas) is True
    row = canvas[2].astype(int)
    assert tuple(row[0]) == _RED
    assert tuple(row[20]) == pytest.approx(_GREEN, abs=20)
    assert tuple(row[39]) == _BLUE


def test_a_deleted_gradient_falls_back_to_foreground_and_background():
    state = ts.load_tool_state()
    state.set_foreground((255, 255, 0))
    state.set_background((0, 0, 0))
    state.set_gradient(name="gone")
    canvas = np.zeros((4, 40, 4), np.uint8)
    _drag(GradientTool(state), canvas)
    assert tuple(canvas[2, 0, :3]) == (255, 255, 0)


def test_the_choice_is_remembered():
    state = ts.load_tool_state()
    events = []
    state.subscribe(events.append)
    assert state.set_gradient(name="sunset") is True
    assert state.set_gradient(name="sunset") is False
    assert events == [ts.EVENT_GRADIENT]
    assert ts.ToolState.from_dict(state.to_dict()).gradient_name == "sunset"
    assert ts.ToolState.from_dict({}).gradient_name == ""


# --- the editor dialog ------------------------------------------------------------

@pytest.fixture
def dialog(qapp):
    save_gradients([_three_stops(), default_gradient("plain")])
    widget = GradientEditorDialog(None, selected="plain")
    yield widget
    widget.deleteLater()


def test_the_dialog_opens_on_the_selected_gradient(dialog):
    assert dialog.selected_name() == "plain"
    assert dialog._stops.count() == 2
    assert not dialog._position.isEnabled() and not dialog._remove_btn.isEnabled()
    assert dialog._preview.pixmap().width() == 256


def test_new_names_the_gradient_after_the_ones_there(dialog):
    dialog._new_btn.click()
    dialog._new_btn.click()
    assert [g.name for g in dialog.gradients()][-2:] == ["Gradient", "Gradient 2"]
    assert dialog.selected_name() == "Gradient 2"


def test_adding_moving_and_removing_a_stop(dialog):
    dialog._add_btn.click()
    assert [round(s.position, 2) for s in dialog.gradients()[1].stops] == [0.0, 0.5, 1.0]
    assert dialog._position.isEnabled()
    dialog._position.setValue(30)
    assert dialog.gradients()[1].stops[1].position == pytest.approx(0.3)
    dialog._remove_btn.click()
    assert len(dialog.gradients()[1].stops) == 2


def test_picking_a_colour_recolours_the_stop(dialog, monkeypatch):
    monkeypatch.setattr(QColorDialog, "getColor", lambda *a, **k: QColor(10, 20, 30, 40))
    dialog._pick_colour()
    assert dialog.gradients()[1].stops[0].color == (10, 20, 30, 40)


def test_a_taken_or_empty_name_is_refused(dialog):
    for name in ("sunset", "  "):
        dialog._name.setText(name)
        dialog._rename()
        assert dialog.selected_name() == "plain"
    dialog._name.setText("dusk")
    dialog._rename()
    assert dialog.selected_name() == "dusk"
    assert dialog._list.currentItem().text() == "dusk"


def test_ok_saves_and_cancel_does_not(dialog, qapp):
    dialog._delete_btn.click()
    assert [g.name for g in dialog.gradients()] == ["sunset"]
    dialog.reject()
    assert [g.name for g in load_gradients()] == ["sunset", "plain"]
    dialog._save()
    assert [g.name for g in load_gradients()] == ["sunset"]


def test_deleting_the_last_gradient_empties_the_editor(qapp):
    save_gradients([default_gradient("only")])
    widget = GradientEditorDialog(None)
    try:
        widget._delete_btn.click()
        assert widget.gradients() == []
        assert widget.selected_name() == ""
        assert not widget._editor.isEnabled() and not widget._delete_btn.isEnabled()
    finally:
        widget.deleteLater()


def test_a_new_gradient_runs_from_the_given_colours(qapp):
    widget = GradientEditorDialog(None, start=(9, 8, 7), end=(1, 2, 3))
    try:
        widget._new_btn.click()
        assert [s.color for s in widget.gradients()[-1].stops] == [(9, 8, 7, 255), (1, 2, 3, 255)]
    finally:
        widget.deleteLater()


# --- the Options bar ---------------------------------------------------------------

def test_the_options_bar_lists_and_picks_saved_gradients(qapp):
    save_gradients([_three_stops()])
    state = ts.load_tool_state()
    bar = PaintOptionsBar(state)
    try:
        combo = bar._gradient_colours
        assert [combo.itemData(i) for i in range(combo.count())] == ["", "sunset"]
        combo.setCurrentIndex(1)
        assert state.gradient_name == "sunset"
        state.set_gradient(name="")
        assert combo.currentIndex() == 0
        state.set_gradient(name="missing")
        assert combo.currentIndex() == 0
    finally:
        bar.deleteLater()
