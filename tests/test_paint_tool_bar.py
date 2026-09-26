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
    listed = [entry for entry in TOOL_ORDER if entry is not None]
    assert len(listed) == len(set(listed))
    listed = set(listed)
    assert listed == set(ts.TOOLS)


def test_tool_order_separators_are_none():
    # Must contain at least one separator so the visual grouping survives
    # if someone reorders entries.
    assert any(entry is None for entry in TOOL_ORDER)


def test_toolbar_buttons_show_the_menu_key_without_binding_it(qapp, state):
    """The Tools menu owns the tool keys; a second QAction on the same key
    would make Qt see the key as ambiguous and fire neither."""
    from Imervue.paint.tools_menu import tool_shortcut

    bar = PaintToolBar(state)
    try:
        for tool in ts.TOOLS:
            action = bar.action_for(tool)
            assert action.shortcut().isEmpty(), tool
            key = tool_shortcut(tool)
            assert action.toolTip().endswith(f"({key})") == bool(key), (tool, action.toolTip())
    finally:
        bar.deleteLater()


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


# ---------------------------------------------------------------------------
# Phase 1 tooltip coverage on the options bar — the brush strip is
# the always-visible default, so every control has to advertise what
# it does on hover. The other strips (fill / selection / text /
# gradient) are stamped out on demand and so verified via their own
# builders rather than the live bar.
# ---------------------------------------------------------------------------


def test_options_bar_brush_strip_widgets_have_tooltips(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        assert bar._brush_size.toolTip()
        assert bar._brush_opacity.toolTip()
        assert bar._brush_hardness.toolTip()
    finally:
        bar.deleteLater()



# ---------------------------------------------------------------------------
# Fill / selection / gradient strips drive ToolState (they used to be inert)
# ---------------------------------------------------------------------------


def test_fill_strip_writes_back_and_starts_from_the_state(qapp, state):
    """The strip showed "Contiguous" unticked while the fill was contiguous, and changed nothing."""
    bar = PaintOptionsBar(state)
    try:
        assert bar._fill_contiguous.isChecked() is state.fill.contiguous  # noqa: SLF001
        assert bar._fill_tolerance.value() == state.fill.tolerance  # noqa: SLF001
        bar._fill_tolerance.setValue(90)  # noqa: SLF001
        bar._fill_contiguous.setChecked(False)  # noqa: SLF001
        bar._fill_all_layers.setChecked(True)  # noqa: SLF001
        assert (state.fill.tolerance, state.fill.contiguous, state.fill.sample_all_layers) == (
            90, False, True)
    finally:
        bar.deleteLater()


def test_selection_mode_combo_sets_the_mode(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        combo = bar._select_mode  # noqa: SLF001
        combo.setCurrentIndex(combo.findData("subtract"))
        assert state.selection_mode == "subtract"
    finally:
        bar.deleteLater()


def test_gradient_strip_sets_kind_and_reverse(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        combo = bar._gradient_kind  # noqa: SLF001
        combo.setCurrentIndex(combo.findData("diamond"))
        bar._gradient_reverse.setChecked(True)  # noqa: SLF001
        assert (state.gradient_kind, state.gradient_reverse) == ("diamond", True)
    finally:
        bar.deleteLater()


def test_the_strips_follow_changes_made_elsewhere(qapp, state):
    bar = PaintOptionsBar(state)
    try:
        state.set_selection_mode("intersect")
        state.set_gradient(kind="radial")
        state.set_fill(tolerance=7)
        assert bar._select_mode.currentData() == "intersect"  # noqa: SLF001
        assert bar._gradient_kind.currentData() == "radial"  # noqa: SLF001
        assert bar._fill_tolerance.value() == 7  # noqa: SLF001
    finally:
        bar.deleteLater()


def test_the_text_tool_has_no_inert_strip(qapp, state):
    """The text strip's font / size / bold / italic did nothing; the Add Text dialog has them."""
    bar = PaintOptionsBar(state)
    try:
        state.set_tool("text")
        text_page = bar._stack.currentIndex()  # noqa: SLF001
        state.set_tool("hand")
        assert bar._stack.currentIndex() == text_page  # noqa: SLF001 - the shared empty page
    finally:
        bar.deleteLater()


def test_every_tool_has_an_options_page(qapp, state):
    """Quick Select had no page, so the bar kept showing the previous tool's options."""
    bar = PaintOptionsBar(state)
    try:
        assert set(bar._page_for_tool) == set(ts.TOOLS)  # noqa: SLF001
        state.set_tool("gradient")
        state.set_tool("select_quick")
        assert bar._stack.currentIndex() == bar._page_for_tool["select_rect"]  # noqa: SLF001
    finally:
        bar.deleteLater()
