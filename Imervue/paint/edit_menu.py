"""Edit-menu actions for the Paint workspace.

Phase 24e introduces the Edit menu with a single Quick Mask Mode
toggle — future selection / clipboard verbs (Cut, Copy, Paste,
Select All) plug in here too.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def populate_edit_menu(workspace: PaintWorkspace) -> None:
    """Attach the Edit-menu actions to ``workspace``."""
    bridge = _EditMenuBridge(workspace)
    workspace._edit_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "edit")
    lang = language_wrapper.language_word_dict

    quick_mask_action = menu.addAction(
        lang.get("paint_edit_quick_mask", "Quick Mask Mode"),
    )
    quick_mask_action.setCheckable(True)
    quick_mask_action.setShortcut(QKeySequence("Q"))
    quick_mask_action.triggered.connect(bridge.toggle_quick_mask)
    bridge._quick_mask_action = quick_mask_action  # noqa: SLF001


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _EditMenuBridge:
    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace
        self._quick_mask_action = None

    def toggle_quick_mask(self) -> None:
        """Flip the workspace's quick-mask mode and sync the action's
        check state."""
        was_active = self._workspace.is_quick_mask_active()
        if was_active:
            self._workspace.exit_quick_mask()
        else:
            self._workspace.enter_quick_mask()
        if self._quick_mask_action is not None:
            self._quick_mask_action.setChecked(
                self._workspace.is_quick_mask_active(),
            )
