"""Tests for the Settings menu and its dialog-launching bridge."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.settings_menu import _SettingsMenuBridge
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop("paint_shortcuts", None)
    user_setting_dict.pop("paint_workspace_presets", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop("paint_shortcuts", None)
    user_setting_dict.pop("paint_workspace_presets", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Menu population
# ---------------------------------------------------------------------------


def test_settings_menu_lists_documented_actions(qapp):
    ws = PaintWorkspace()
    try:
        settings_menu = menu_for(ws, "settings")
        # Three top entries + 1 separator + Liquify = 5 actions.
        assert len(settings_menu.actions()) == 5
    finally:
        ws.deleteLater()


def test_settings_menu_actions_have_translated_labels(qapp):
    ws = PaintWorkspace()
    try:
        settings_menu = menu_for(ws, "settings")
        labels = [
            a.text() for a in settings_menu.actions()
            if not a.isSeparator()
        ]
        for label in labels:
            assert not label.startswith("paint_settings_"), label
    finally:
        ws.deleteLater()


def test_workspace_holds_bridge_reference(qapp):
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._settings_menu_bridge, _SettingsMenuBridge)  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge — open_pressure_curve
# ---------------------------------------------------------------------------


def test_open_pressure_curve_creates_dialog(qapp, monkeypatch):
    """Open the pressure-curve dialog and immediately close it via
    monkeypatched ``exec``; after Accepted the workspace state's
    ``pressure_curve`` is set."""
    from Imervue.paint.pressure_curve import PressureCurve
    from Imervue.paint.pressure_curve_dialog import PressureCurveDialog

    # Tracker that captures the dialog and forces Accepted.
    captured = {}
    original_exec = PressureCurveDialog.exec

    def fake_exec(self):
        captured["dialog"] = self
        return PressureCurveDialog.DialogCode.Accepted

    monkeypatch.setattr(PressureCurveDialog, "exec", fake_exec)
    ws = PaintWorkspace()
    try:
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_pressure_curve()
        assert "dialog" in captured
        assert isinstance(ws.state().pressure_curve, PressureCurve)
    finally:
        # Restore exec so other tests aren't affected.
        monkeypatch.setattr(PressureCurveDialog, "exec", original_exec)
        ws.deleteLater()


def test_open_pressure_curve_cancel_does_not_assign_state(qapp, monkeypatch):
    from Imervue.paint.pressure_curve_dialog import PressureCurveDialog
    monkeypatch.setattr(
        PressureCurveDialog, "exec",
        lambda self: PressureCurveDialog.DialogCode.Rejected,
    )
    ws = PaintWorkspace()
    try:
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_pressure_curve()
        # No assignment because the dialog was cancelled.
        assert not hasattr(ws.state(), "pressure_curve")
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge — open_shortcuts
# ---------------------------------------------------------------------------


def test_open_shortcuts_persists_on_accept(qapp, monkeypatch):
    from Imervue.paint.shortcut_dialog import ShortcutDialog

    def fake_exec(self):
        # Mutate the working registry before Accepted so we can verify
        # it gets persisted.
        self.registry().set("paint.tool.brush", "Ctrl+Q")
        return ShortcutDialog.DialogCode.Accepted

    monkeypatch.setattr(ShortcutDialog, "exec", fake_exec)
    ws = PaintWorkspace()
    try:
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_shortcuts()
        from Imervue.paint.shortcut_registry import load_shortcuts
        assert load_shortcuts().get("paint.tool.brush") == "Ctrl+Q"
    finally:
        ws.deleteLater()


def test_open_shortcuts_cancel_does_not_persist(qapp, monkeypatch):
    from Imervue.paint.shortcut_dialog import ShortcutDialog

    def fake_exec(self):
        self.registry().set("paint.tool.brush", "Ctrl+Q")
        return ShortcutDialog.DialogCode.Rejected

    monkeypatch.setattr(ShortcutDialog, "exec", fake_exec)
    ws = PaintWorkspace()
    try:
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_shortcuts()
        from Imervue.paint.shortcut_registry import load_shortcuts
        # Default still in place because we cancelled.
        assert load_shortcuts().get("paint.tool.brush") == "B"
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge — open_workspace_presets
# ---------------------------------------------------------------------------


def test_open_workspace_presets_runs_dialog(qapp, monkeypatch):
    from Imervue.paint.workspace_preset_dialog import WorkspacePresetDialog
    captured = {"opened": False}

    def fake_exec(self):
        captured["opened"] = True
        return WorkspacePresetDialog.DialogCode.Accepted

    monkeypatch.setattr(WorkspacePresetDialog, "exec", fake_exec)
    ws = PaintWorkspace()
    try:
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_workspace_presets()
        assert captured["opened"]
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge — open_liquify
# ---------------------------------------------------------------------------


def test_open_liquify_writes_back_on_accept(qapp, monkeypatch):
    """Verify that ``open_liquify`` copies the dialog's working_image
    into the active layer when the user accepts."""
    import numpy as np

    from Imervue.paint.liquify_dialog import LiquifyDialog
    captured = {}

    def fake_exec(self):
        # Mutate the working buffer so we can detect the writeback.
        self.working_image()[0, 0] = (123, 45, 67, 255)
        captured["dialog"] = self
        return LiquifyDialog.DialogCode.Accepted

    monkeypatch.setattr(LiquifyDialog, "exec", fake_exec)
    ws = PaintWorkspace()
    try:
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_liquify()
        assert "dialog" in captured
        # Active layer's pixel matches what the dialog wrote.
        layer = ws.canvas().document().active_layer()
        np.testing.assert_array_equal(layer.image[0, 0], (123, 45, 67, 255))
    finally:
        ws.deleteLater()


def test_open_liquify_cancel_does_not_modify_active_layer(qapp, monkeypatch):
    import numpy as np

    from Imervue.paint.liquify_dialog import LiquifyDialog

    def fake_exec(self):
        self.working_image()[0, 0] = (200, 0, 0, 255)
        return LiquifyDialog.DialogCode.Rejected

    monkeypatch.setattr(LiquifyDialog, "exec", fake_exec)
    ws = PaintWorkspace()
    try:
        layer = ws.canvas().document().active_layer()
        before = layer.image[0, 0].copy()
        bridge = ws._settings_menu_bridge   # noqa: SLF001
        bridge.open_liquify()
        np.testing.assert_array_equal(layer.image[0, 0], before)
    finally:
        ws.deleteLater()
