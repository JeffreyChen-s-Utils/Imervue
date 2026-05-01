"""Layer-menu actions for the Paint workspace.

Wires the existing :class:`PaintDocument` verbs to one-click menu
entries with conventional shortcuts:

* Add raster layer (Ctrl+Shift+N) — :meth:`PaintDocument.add_layer`
* Add vector layer (Ctrl+Shift+V) — :meth:`PaintDocument.add_vector_layer`
* Duplicate layer (Ctrl+J) — :meth:`PaintDocument.duplicate_active_layer`
* Merge down (Ctrl+E) — :meth:`PaintDocument.merge_down`
* Delete layer (Ctrl+Shift+Delete) — :meth:`PaintDocument.remove_active_layer`

The bridge class follows the same pattern as
:mod:`Imervue.paint.file_menu` so the workspace holds one strong
reference (``_layer_menu_bridge``) for every action.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def populate_layer_menu(workspace: PaintWorkspace) -> None:
    """Attach Layer-menu actions to ``workspace``."""
    bridge = _LayerMenuBridge(workspace)
    workspace._layer_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "layer")
    lang = language_wrapper.language_word_dict
    for key, fallback, slot, shortcut in (
        ("paint_layer_add_raster", "Add Layer",
         bridge.add_raster_layer, "Ctrl+Shift+N"),
        ("paint_layer_add_vector", "Add Vector Layer",
         bridge.add_vector_layer, "Ctrl+Shift+V"),
        ("paint_layer_duplicate", "Duplicate Layer",
         bridge.duplicate_layer, "Ctrl+J"),
        ("paint_layer_merge_down", "Merge Down",
         bridge.merge_down, "Ctrl+E"),
        (None, None, None, None),
        ("paint_layer_delete", "Delete Layer",
         bridge.delete_layer, "Ctrl+Shift+Backspace"),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _LayerMenuBridge:
    """Routes Layer-menu actions to the document + canvas refresh."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def add_raster_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        document.add_layer()
        self._refresh_canvas()

    def add_vector_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        document.add_vector_layer()
        self._refresh_canvas()

    def duplicate_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.active_layer() is None:
            return
        document.duplicate_active_layer()
        self._refresh_canvas()

    def merge_down(self) -> None:
        document = self._workspace.canvas().document()
        if document.merge_down():
            self._refresh_canvas()

    def delete_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.layer_count <= 1:
            # Refuse to drop the last layer — matches the document
            # model's own invariant.
            return
        document.remove_active_layer()
        self._refresh_canvas()

    # ---- internals ------------------------------------------------------

    def _refresh_canvas(self) -> None:
        canvas = self._workspace.canvas()
        canvas.document().invalidate_composite()
        canvas.update()
