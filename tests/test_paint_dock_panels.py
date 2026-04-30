"""Qt smoke tests for the Paint workspace dock panels."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.color_math import rgb_to_hex
from Imervue.paint.dock_panels import (
    BrushDock,
    ColorDock,
    HistoryDock,
    LayerDock,
    NavigatorDock,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    return ts.load_tool_state()


# ---------------------------------------------------------------------------
# ColorDock
# ---------------------------------------------------------------------------


def test_color_dock_constructs(qapp, state):
    dock = ColorDock(state)
    try:
        assert dock.windowTitle() != ""
    finally:
        dock.deleteLater()


def test_color_dock_initial_hex_matches_state(qapp, state):
    state.set_foreground((100, 50, 25))
    dock = ColorDock(state)
    try:
        assert dock._hex_edit.text() == rgb_to_hex((100, 50, 25))
    finally:
        dock.deleteLater()


def test_color_dock_responds_to_state_color_event(qapp, state):
    dock = ColorDock(state)
    try:
        state.set_foreground((20, 40, 60))
        assert dock._r_slider.value() == 20
        assert dock._g_slider.value() == 40
        assert dock._b_slider.value() == 60
    finally:
        dock.deleteLater()


def test_color_dock_rgb_slider_writes_back_to_state(qapp, state):
    dock = ColorDock(state)
    try:
        dock._r_slider.setValue(123)
        assert state.foreground[0] == 123
    finally:
        dock.deleteLater()


def test_color_dock_history_swatches_match_state(qapp, state):
    for rgb in [(10, 0, 0), (20, 0, 0), (30, 0, 0)]:
        state.set_foreground(rgb)
    dock = ColorDock(state)
    try:
        layout = dock._history_grid.layout()
        assert layout.count() == len(state.color_history)
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# BrushDock
# ---------------------------------------------------------------------------


def test_brush_dock_constructs(qapp, state):
    dock = BrushDock(state)
    try:
        assert dock.windowTitle() != ""
    finally:
        dock.deleteLater()


def test_brush_dock_size_slider_writes_back_to_state(qapp, state):
    dock = BrushDock(state)
    try:
        dock._size.setValue(80)
        assert state.brush.size == 80
    finally:
        dock.deleteLater()


def test_brush_dock_kind_combo_writes_back_to_state(qapp, state):
    dock = BrushDock(state)
    try:
        dock._kind.setCurrentIndex(dock._kind.findData("airbrush"))
        assert state.brush.kind == "airbrush"
    finally:
        dock.deleteLater()


def test_brush_dock_blend_combo_writes_back_to_state(qapp, state):
    dock = BrushDock(state)
    try:
        dock._blend.setCurrentIndex(dock._blend.findData("multiply"))
        assert state.brush.blend_mode == "multiply"
    finally:
        dock.deleteLater()


def test_brush_dock_responds_to_state_brush_event(qapp, state):
    dock = BrushDock(state)
    try:
        state.set_brush(size=66, opacity=0.5)
        assert dock._size.value() == 66
        assert dock._opacity.value() == 50
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# LayerDock / NavigatorDock / HistoryDock — placeholder smoke tests
# ---------------------------------------------------------------------------


def test_layer_dock_constructs(qapp):
    dock = LayerDock()
    try:
        assert dock.windowTitle() != ""
    finally:
        dock.deleteLater()


def test_navigator_dock_constructs(qapp):
    dock = NavigatorDock()
    try:
        assert dock.windowTitle() != ""
    finally:
        dock.deleteLater()


def test_navigator_set_zoom_does_not_re_emit(qapp):
    dock = NavigatorDock()
    try:
        seen = []
        dock.zoom_changed.connect(seen.append)
        dock.set_zoom(2.5)
        assert seen == []
        assert dock._zoom_slider.value() == 250
    finally:
        dock.deleteLater()


def test_history_dock_constructs_and_populates(qapp):
    dock = HistoryDock()
    try:
        dock.set_states(["open", "stroke", "blur"], current_index=1)
        assert dock._list.count() == 3
        assert dock._list.currentRow() == 1
    finally:
        dock.deleteLater()


def test_history_dock_empty_state_shows_hint(qapp):
    dock = HistoryDock()
    try:
        dock.set_states([], current_index=-1)
        assert dock._hint.isVisible() is True or dock._list.count() == 0
    finally:
        dock.deleteLater()
