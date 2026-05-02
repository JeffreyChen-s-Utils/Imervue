"""Top-level menu bar for the Paint workspace.

Builds the standard File / Edit / Layer / View / Tools / Filter /
Settings / Window menu structure and returns the assembled
:class:`QMenuBar`. Each top-level menu's actions are populated by
its own builder module so this file stays focused on layout.

Phases 21b–21g attach actions to the empty menus this module
provides; the builders here are intentionally minimal so a new
sub-phase can hang its actions without touching any other phase.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu, QMenuBar

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.filter_menu import build_filter_menu

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace

# Translation key per top-level menu. Documented here so a new
# language file can extend the set without grepping the workspace.
MENU_KEYS: tuple[tuple[str, str], ...] = (
    ("file", "paint_menu_file"),
    ("edit", "paint_menu_edit"),
    ("image", "paint_menu_image"),
    ("layer", "paint_menu_layer"),
    ("view", "paint_menu_view"),
    ("tools", "paint_menu_tools"),
    ("filter", "paint_menu_filter"),
    ("manga", "paint_menu_manga"),
    ("settings", "paint_menu_settings"),
    ("window", "paint_menu_window"),
)
_MENU_FALLBACKS: dict[str, str] = {
    "file": "File",
    "edit": "Edit",
    "image": "Image",
    "layer": "Layer",
    "view": "View",
    "tools": "Tools",
    "filter": "Filter",
    "manga": "Manga",
    "settings": "Settings",
    "window": "Window",
}


def build_paint_menu_bar(workspace: PaintWorkspace) -> QMenuBar:
    """Construct the workspace's :class:`QMenuBar`.

    Each top-level menu is stored on the workspace as
    ``_<key>_menu`` so 21b–21g can populate them via
    :func:`menu_for(workspace, key)` without re-walking the bar's
    children list.
    """
    bar = QMenuBar(workspace)
    lang = language_wrapper.language_word_dict
    for key, label_key in MENU_KEYS:
        if key == "filter":
            menu = build_filter_menu(workspace)
        else:
            label = lang.get(label_key, _MENU_FALLBACKS[key])
            menu = QMenu(label, workspace)
        bar.addMenu(menu)
        setattr(workspace, f"_{key}_menu", menu)
    return bar


def menu_for(workspace: PaintWorkspace, key: str) -> QMenu:
    """Look up a previously-built menu by its short key.

    Sub-phase builders use this so they don't have to reach into
    private attributes directly. Raises ``KeyError`` for unknown
    keys so a typo can't silently route an action into nothing.
    """
    if key not in {k for k, _label in MENU_KEYS}:
        raise KeyError(
            f"unknown menu key {key!r}; expected one of "
            f"{tuple(k for k, _ in MENU_KEYS)}",
        )
    return getattr(workspace, f"_{key}_menu")
