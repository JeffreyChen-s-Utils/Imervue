"""Tools menu — one menu entry per active tool.

Mirrors the left-side toolbar but with keyboard shortcuts so users
can switch tools without reaching for the mouse. The action
catalogue is a hand-curated subset of :data:`TOOLS` because most
users never touch tools like ``blur`` directly; the toolbar still
exposes them for power users.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


@dataclass(frozen=True)
class ToolEntry:
    """One entry on the Tools menu — tool id + label key + shortcut."""

    tool_id: str
    label_key: str
    shortcut: str


# Conventional MediBang / Photoshop keybindings. ``bezier_pen`` and
# ``clone_stamp`` follow the same convention (P for pen, S for stamp).
TOOL_ENTRIES: tuple[ToolEntry, ...] = (
    ToolEntry("brush", "paint_tool_brush", "B"),
    ToolEntry("eraser", "paint_tool_eraser", "E"),
    ToolEntry("eyedropper", "paint_tool_eyedropper", "I"),
    ToolEntry("fill", "paint_tool_fill", "G"),
    ToolEntry("move", "paint_tool_move", "V"),
    ToolEntry("text", "paint_tool_text", "T"),
    ToolEntry("gradient", "paint_tool_gradient", "U"),
    ToolEntry("smudge", "paint_tool_smudge", "R"),
    ToolEntry("bezier_pen", "paint_tool_bezier_pen", "P"),
    ToolEntry("clone_stamp", "paint_tool_clone_stamp", "S"),
    ToolEntry("speech_bubble", "paint_tool_speech_bubble", "Ctrl+B"),
    ToolEntry("shape_rect", "paint_tool_shape_rect", "Shift+R"),
    ToolEntry("shape_ellipse", "paint_tool_shape_ellipse", "Shift+E"),
    ToolEntry("shape_line", "paint_tool_shape_line", "Shift+I"),
    ToolEntry("shape_polygon", "paint_tool_shape_polygon", "Shift+P"),
    ToolEntry("crop", "paint_tool_crop", "C"),
    ToolEntry("transform", "paint_tool_transform", "Ctrl+T"),
    ToolEntry("hand", "paint_tool_hand", "H"),
    ToolEntry("zoom", "paint_tool_zoom", "Z"),
)

_FALLBACKS: dict[str, str] = {
    "paint_tool_brush": "Brush",
    "paint_tool_eraser": "Eraser",
    "paint_tool_eyedropper": "Eyedropper",
    "paint_tool_fill": "Fill",
    "paint_tool_move": "Move",
    "paint_tool_text": "Text",
    "paint_tool_gradient": "Gradient",
    "paint_tool_smudge": "Smudge",
    "paint_tool_bezier_pen": "Bezier Pen",
    "paint_tool_clone_stamp": "Clone Stamp",
    "paint_tool_speech_bubble": "Speech Bubble",
    "paint_tool_shape_rect": "Rectangle",
    "paint_tool_shape_ellipse": "Ellipse",
    "paint_tool_shape_line": "Line",
    "paint_tool_shape_polygon": "Polygon",
    "paint_tool_crop": "Crop",
    "paint_tool_transform": "Transform",
    "paint_tool_hand": "Hand",
    "paint_tool_zoom": "Zoom",
}


def populate_tools_menu(workspace: PaintWorkspace) -> None:
    """Attach the documented Tools-menu actions to ``workspace``."""
    bridge = _ToolsMenuBridge(workspace)
    workspace._tools_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "tools")
    lang = language_wrapper.language_word_dict
    bridge._actions = {}   # noqa: SLF001
    for entry in TOOL_ENTRIES:
        action = menu.addAction(
            lang.get(entry.label_key, _FALLBACKS[entry.label_key]),
        )
        action.setShortcut(QKeySequence(entry.shortcut))
        action.setCheckable(True)
        action.triggered.connect(
            lambda _checked=False, t=entry.tool_id: bridge.activate(t),
        )
        bridge._actions[entry.tool_id] = action   # noqa: SLF001
    bridge.refresh_check_states()
    # Update the check state whenever the user picks a different tool
    # via the toolbar / shortcut so the menu stays in sync.
    workspace.state().subscribe(bridge._on_state_event)   # noqa: SLF001


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _ToolsMenuBridge:
    """Routes Tools-menu actions to ToolState.set_tool()."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def activate(self, tool_id: str) -> None:
        self._workspace.state().set_tool(tool_id)

    def refresh_check_states(self) -> None:
        active = self._workspace.state().tool
        for tool_id, action in self._actions.items():
            action.setChecked(tool_id == active)

    def _on_state_event(self, channel: str) -> None:
        from Imervue.paint.tool_state import EVENT_TOOL
        if channel == EVENT_TOOL:
            self.refresh_check_states()
