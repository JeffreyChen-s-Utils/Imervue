"""Settings menu — launch the existing config dialogs.

Wires the Pressure Curve, Shortcut, Workspace Layout, and Liquify
dialogs (built in 19f / 19k / 19d / 18i) behind menu entries. Each
slot opens the dialog modally; on accept the result is committed
back into ToolState / persistent storage / the active layer.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace

logger = logging.getLogger("Imervue.paint.settings_menu")


def populate_settings_menu(workspace: PaintWorkspace) -> None:
    """Attach the Settings-menu actions to ``workspace``."""
    bridge = _SettingsMenuBridge(workspace)
    workspace._settings_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "settings")
    lang = language_wrapper.language_word_dict
    for key, fallback, slot in (
        ("paint_settings_pressure_curve", "Pressure Curve…",
         bridge.open_pressure_curve),
        ("paint_settings_shortcuts", "Shortcuts…",
         bridge.open_shortcuts),
        ("paint_settings_shortcut_cheatsheet", "Shortcut Cheat Sheet…",
         bridge.open_shortcut_cheatsheet),
        ("paint_settings_workspace_layouts", "Workspace Layouts…",
         bridge.open_workspace_presets),
        (None, None, None),
        ("paint_settings_liquify", "Liquify Active Layer…",
         bridge.open_liquify),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        action.triggered.connect(slot)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _SettingsMenuBridge:
    """Routes Settings-menu actions to the relevant config dialog."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def open_pressure_curve(self) -> None:
        from Imervue.paint.pressure_curve import PressureCurve
        from Imervue.paint.pressure_curve_dialog import PressureCurveDialog
        state = self._workspace.state()
        current = getattr(state, "pressure_curve", PressureCurve())
        dialog = PressureCurveDialog(curve=current, parent=self._workspace)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # The state may not yet have a pressure_curve field; assign
            # via setattr so an older state schema doesn't crash.
            state.pressure_curve = dialog.curve()

    def open_shortcuts(self) -> None:
        from Imervue.paint.shortcut_dialog import ShortcutDialog
        from Imervue.paint.shortcut_registry import (
            load_shortcuts, save_shortcuts,
        )
        registry = load_shortcuts()
        dialog = ShortcutDialog(registry=registry, parent=self._workspace)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            save_shortcuts(dialog.registry())

    def open_shortcut_cheatsheet(self) -> None:
        """Read-only listing of every menu shortcut bound on the
        workspace. Discoverability fix — most shortcuts live in
        the menus and would otherwise stay invisible."""
        from Imervue.paint.shortcuts_dialog import open_shortcuts_dialog
        open_shortcuts_dialog(self._workspace, parent=self._workspace)

    def open_workspace_presets(self) -> None:
        from Imervue.paint.workspace_preset_dialog import (
            WorkspacePresetDialog,
            apply_workspace_preset,
        )
        from Imervue.paint.workspace_presets import all_workspace_presets
        dialog = WorkspacePresetDialog(parent=self._workspace)

        def _on_apply(name: str) -> None:
            preset = next(
                (p for p in all_workspace_presets() if p.name == name), None,
            )
            if preset is None:
                return
            apply_workspace_preset(self._workspace, preset)

        dialog.apply_requested.connect(_on_apply)
        dialog.exec()

    def open_liquify(self) -> None:
        import numpy as np

        from Imervue.paint.liquify_dialog import LiquifyDialog
        layer = self._workspace.canvas().document().active_layer()
        if layer is None:
            return
        dialog = LiquifyDialog(layer.image, parent=self._workspace)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            np.copyto(layer.image, dialog.working_image())
            self._workspace.canvas().document().invalidate_composite()
            self._workspace.canvas().update()
