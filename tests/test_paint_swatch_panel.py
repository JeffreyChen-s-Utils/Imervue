"""Tests for the floating swatch panel."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.swatch_panel import SwatchPanel
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state_with_history():
    state = ts.load_tool_state()
    # Push three distinct colours into history via the documented
    # set_foreground commit path.
    for rgb in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        state.set_foreground(rgb, commit=True)
    return state


# ---------------------------------------------------------------------------
# Construction + refresh
# ---------------------------------------------------------------------------


def test_panel_grid_populates_from_history(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        assert panel._grid.count() == 3  # noqa: SLF001
    finally:
        panel.deleteLater()


def test_panel_refreshes_on_history_event(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        before = panel._grid.count()  # noqa: SLF001
        state_with_history.set_foreground((10, 20, 30), commit=True)
        assert panel._grid.count() == before + 1  # noqa: SLF001
    finally:
        panel.deleteLater()


def test_panel_clear_drops_every_swatch(qapp, state_with_history, monkeypatch):
    panel = SwatchPanel(state_with_history)
    try:
        # Phase 36p — _on_clear now confirms first; bypass the modal.
        monkeypatch.setattr(panel, "_confirm_clear", lambda: True)
        panel._on_clear()  # noqa: SLF001
        assert panel._grid.count() == 0  # noqa: SLF001
        assert state_with_history.color_history == []
    finally:
        panel.deleteLater()


def test_panel_clear_cancel_keeps_swatches(qapp, state_with_history, monkeypatch):
    panel = SwatchPanel(state_with_history)
    try:
        before = list(state_with_history.color_history)
        monkeypatch.setattr(panel, "_confirm_clear", lambda: False)
        panel._on_clear()  # noqa: SLF001
        assert state_with_history.color_history == before
    finally:
        panel.deleteLater()


def test_panel_clear_skips_prompt_on_empty_history(qapp, monkeypatch):
    """When the history is already empty, the confirmation isn't
    worth running — nothing would be lost. Use a sentinel raise to
    fail the test if the prompt fires."""
    from Imervue.paint import tool_state as ts
    state = ts.load_tool_state()
    state.color_history.clear()
    panel = SwatchPanel(state)
    try:
        def _should_not_run():
            raise AssertionError("confirm prompt fired on empty history")

        monkeypatch.setattr(panel, "_confirm_clear", _should_not_run)
        panel._on_clear()   # noqa: SLF001
        assert state.color_history == []
    finally:
        panel.deleteLater()


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


def test_reorder_moves_swatch_in_history(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        before = list(state_with_history.color_history)
        panel.reorder(0, 2)
        after = list(state_with_history.color_history)
        # The first colour migrated to position 2; the others shifted up.
        assert after[2] == before[0]
        assert after[0] == before[1]
        assert after[1] == before[2]
    finally:
        panel.deleteLater()


def test_reorder_idempotent_for_same_index(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        assert panel.reorder(1, 1) is False
    finally:
        panel.deleteLater()


def test_reorder_returns_false_for_out_of_range(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        assert panel.reorder(99, 0) is False
        assert panel.reorder(0, 99) is False
    finally:
        panel.deleteLater()


def test_reorder_emits_history_event(qapp, state_with_history):
    """Reordering must fire the history channel so other dock
    panels (e.g. ColorDock's swatch row) re-pull the new ordering."""
    received: list[str] = []
    state_with_history.subscribe(lambda channel: received.append(channel))
    panel = SwatchPanel(state_with_history)
    try:
        panel.reorder(0, 2)
        assert "color_history" in received
    finally:
        panel.deleteLater()


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


def test_remove_at_drops_single_colour(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        before = list(state_with_history.color_history)
        panel.remove_at(1)
        after = list(state_with_history.color_history)
        assert before[1] not in after
        assert len(after) == len(before) - 1
    finally:
        panel.deleteLater()


def test_remove_at_returns_false_out_of_range(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        assert panel.remove_at(99) is False
    finally:
        panel.deleteLater()


# ---------------------------------------------------------------------------
# Click → state change
# ---------------------------------------------------------------------------


def test_swatch_click_updates_foreground(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        first_rgb = state_with_history.color_history[0]
        # Pretend the user clicked the matching swatch by calling
        # the slot directly (skipping the QToolButton click → signal).
        panel._on_swatch_clicked(first_rgb)  # noqa: SLF001
        assert state_with_history.foreground == first_rgb
    finally:
        panel.deleteLater()


def test_swatch_click_emits_color_chosen_signal(qapp, state_with_history):
    panel = SwatchPanel(state_with_history)
    try:
        emitted: list[tuple[int, int, int]] = []
        panel.color_chosen.connect(lambda r, g, b: emitted.append((r, g, b)))
        panel._on_swatch_clicked((1, 2, 3))  # noqa: SLF001
        assert emitted == [(1, 2, 3)]
    finally:
        panel.deleteLater()
