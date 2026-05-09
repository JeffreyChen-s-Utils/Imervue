"""Tests for the custom brush preset manager dialog.

The dialog drives ``ToolState`` sub-tools — covered exhaustively at
the state level elsewhere — so we only verify the Qt wiring:

* The list reflects the live sub-tool registry on construction and
  on every mutation triggered by a button.
* Save captures the current brush settings and stores them under
  the typed name.
* Apply round-trips the snapshot back into the live state, firing
  ``EVENT_BRUSH`` / ``EVENT_FILL`` so other docks refresh.
* Rename preserves the snapshot's settings; delete drops it.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QInputDialog

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_preset_dialog import BrushPresetDialog
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _seed_two_presets(state: ts.ToolState) -> None:
    state.set_brush(size=10, opacity=0.5)
    state.add_sub_tool(state.tool, "fine-liner")
    state.set_brush(size=40, opacity=1.0)
    state.add_sub_tool(state.tool, "fat-marker")


def test_dialog_lists_existing_presets_for_active_tool(qapp):
    state = ts.load_tool_state()
    _seed_two_presets(state)
    dialog = BrushPresetDialog(state)
    try:
        names = [
            dialog._list.item(i).text()              # noqa: SLF001
            for i in range(dialog._list.count())     # noqa: SLF001
        ]
        assert names == ["fine-liner", "fat-marker"]
    finally:
        dialog.deleteLater()


def test_dialog_save_captures_current_brush(qapp, monkeypatch):
    state = ts.load_tool_state()
    state.set_brush(size=27, hardness=0.42)
    dialog = BrushPresetDialog(state)
    try:
        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *_a, **_k: ("crisp-ink", True)),
        )
        dialog._on_save()                            # noqa: SLF001

        saved = state.list_sub_tools(state.tool)
        names = [s.name for s in saved]
        assert "crisp-ink" in names
        target = next(s for s in saved if s.name == "crisp-ink")
        assert target.brush.size == 27
        assert target.brush.hardness == pytest.approx(0.42)
    finally:
        dialog.deleteLater()


def test_dialog_apply_swaps_live_state_to_snapshot(qapp):
    state = ts.load_tool_state()
    _seed_two_presets(state)
    dialog = BrushPresetDialog(state)
    try:
        # Mutate live brush then re-apply the first preset; the live
        # state must come back to the snapshot's values.
        state.set_brush(size=99, opacity=0.10)
        for row in range(dialog._list.count()):                 # noqa: SLF001
            if dialog._list.item(row).text() == "fine-liner":   # noqa: SLF001
                dialog._list.setCurrentRow(row)                 # noqa: SLF001
                break
        dialog._on_apply()                                       # noqa: SLF001
        assert state.brush.size == 10
        assert state.brush.opacity == pytest.approx(0.5)
    finally:
        dialog.deleteLater()


def test_dialog_rename_keeps_settings_intact(qapp, monkeypatch):
    state = ts.load_tool_state()
    _seed_two_presets(state)
    dialog = BrushPresetDialog(state)
    try:
        for row in range(dialog._list.count()):                 # noqa: SLF001
            if dialog._list.item(row).text() == "fat-marker":   # noqa: SLF001
                dialog._list.setCurrentRow(row)                 # noqa: SLF001
                break
        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *_a, **_k: ("chunky-marker", True)),
        )
        # Capture the original settings of the preset BEFORE rename to
        # compare against the renamed entry afterwards.
        original = next(
            s for s in state.list_sub_tools(state.tool)
            if s.name == "fat-marker"
        )
        dialog._on_rename()                                      # noqa: SLF001

        names = [s.name for s in state.list_sub_tools(state.tool)]
        assert "fat-marker" not in names
        assert "chunky-marker" in names
        renamed = next(
            s for s in state.list_sub_tools(state.tool)
            if s.name == "chunky-marker"
        )
        assert renamed.brush == original.brush
        assert renamed.fill == original.fill
    finally:
        dialog.deleteLater()


def test_dialog_delete_removes_selected_preset(qapp):
    state = ts.load_tool_state()
    _seed_two_presets(state)
    dialog = BrushPresetDialog(state)
    try:
        for row in range(dialog._list.count()):                 # noqa: SLF001
            if dialog._list.item(row).text() == "fine-liner":   # noqa: SLF001
                dialog._list.setCurrentRow(row)                 # noqa: SLF001
                break
        dialog._on_delete()                                      # noqa: SLF001
        names = [s.name for s in state.list_sub_tools(state.tool)]
        assert names == ["fat-marker"]
    finally:
        dialog.deleteLater()
