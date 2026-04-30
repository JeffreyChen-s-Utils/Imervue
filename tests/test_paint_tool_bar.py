"""Qt smoke tests for the Paint workspace tool bars."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.tool_bar import (
    TOOL_ORDER,
    PaintOptionsBar,
    PaintToolBar,
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
# TOOL_ORDER sanity
# ---------------------------------------------------------------------------


def test_tool_order_lists_every_documented_tool():
    listed = {entry[0] for entry in TOOL_ORDER if entry is not None}
    assert listed == set(ts.TOOLS)


def test_tool_order_separators_are_none():
    # Must contain at least one separator so the visual grouping survives
    # if someone reorders entries.
    assert any(entry is None for entry in TOOL_ORDER)


def test_tool_order_shortcuts_unique_when_present():
    shortcuts = [entry[1] for entry in TOOL_ORDER if entry is not None and entry[1]]
    assert len(shortcuts) == len(set(shortcuts))


# ---------------------------------------------------------------------------
# PaintToolBar
# ---------------------------------------------------------------------------


def test_paint_toolbar_creates_action_per_tool(qapp, state):
    bar = PaintToolBar(state)
    try:
        for tool in ts.TOOLS:
            assert bar.action_for(tool) is not None
    finally:
        bar.deleteLater()


def test_paint_toolbar_initial_selection_matches_state(qapp, state):
    state.set_tool("eraser")
    bar = PaintToolBar(state)
    try:
        assert bar.action_for("eraser").isChecked() is True
        assert bar.action_for("brush").isChecked() is False
    finally:
        bar.deleteLater()


def test_paint_toolbar_emits_tool_picked_when_clicked(qapp, state):
    bar = PaintToolBar(state)
    try:
        seen: list[str] = []
        bar.tool_picked.connect(seen.append)
        bar.action_for("fill").trigger()
        assert seen == ["fill"]
        assert state.tool == "fill"
    finally:
        bar.deleteLater()


def test_paint_toolbar_responds_to_external_state_change(qapp, state):
    bar = PaintToolBar(state)
    try:
        state.set_tool("zoom")
        assert bar.action_for("zoom").isChecked() is True
    finally:
        bar.deleteLater()


# ---------------------------------------------------------------------------
# PaintOptionsBar
# ---------------------------------------------------------------------------


def test_options_bar_constructs(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        assert bar.windowTitle() != ""
    finally:
        bar.deleteLater()


def test_options_bar_swaps_page_on_tool_change(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        brush_page = bar._stack.currentIndex()
        state.set_tool("fill")
        fill_page = bar._stack.currentIndex()
        assert brush_page != fill_page
    finally:
        bar.deleteLater()


def test_options_bar_brush_size_writes_back(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        bar._brush_size.setValue(80)
        assert state.brush.size == 80
    finally:
        bar.deleteLater()


def test_options_bar_brush_opacity_writes_back(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        bar._brush_opacity.setValue(40)
        assert state.brush.opacity == pytest.approx(0.4, abs=1e-3)
    finally:
        bar.deleteLater()


def test_options_bar_refreshes_when_brush_changes(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        state.set_brush(size=120, opacity=0.25, hardness=0.5)
        assert bar._brush_size.value() == 120
        assert bar._brush_opacity.value() == 25
        assert bar._brush_hardness.value() == 50
    finally:
        bar.deleteLater()
