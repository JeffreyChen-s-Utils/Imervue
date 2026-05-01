"""Image-menu actions for the Paint workspace.

Phase 25a populates the new Image menu with whole-canvas verbs:
flip horizontal / flip vertical / rotate 90° CW & CCW / rotate 180°.
Future image-level commands (image size, canvas size) plug in here.

Each action delegates to the existing :class:`PaintDocument`
in-place transforms; the bridge just resolves the active canvas's
document and refreshes after the mutation lands.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def populate_image_menu(workspace: PaintWorkspace) -> None:
    """Attach the Image-menu actions to ``workspace``."""
    bridge = _ImageMenuBridge(workspace)
    workspace._image_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "image")
    lang = language_wrapper.language_word_dict
    for key, fallback, slot, shortcut in (
        ("paint_image_flip_horizontal", "Flip Horizontal",
         bridge.flip_horizontal, ""),
        ("paint_image_flip_vertical", "Flip Vertical",
         bridge.flip_vertical, ""),
        (None, None, None, None),
        ("paint_image_rotate_90_cw", "Rotate 90° CW",
         bridge.rotate_90_cw, ""),
        ("paint_image_rotate_90_ccw", "Rotate 90° CCW",
         bridge.rotate_90_ccw, ""),
        ("paint_image_rotate_180", "Rotate 180°",
         bridge.rotate_180, ""),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _ImageMenuBridge:
    """Routes Image-menu actions to PaintDocument verbs + canvas refresh."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def flip_horizontal(self) -> None:
        document = self._workspace.canvas().document()
        if document.flip_horizontal():
            self._refresh_canvas()

    def flip_vertical(self) -> None:
        document = self._workspace.canvas().document()
        if document.flip_vertical():
            self._refresh_canvas()

    def rotate_90_cw(self) -> None:
        document = self._workspace.canvas().document()
        if document.rotate_90_cw():
            self._refresh_canvas()

    def rotate_90_ccw(self) -> None:
        document = self._workspace.canvas().document()
        if document.rotate_90_ccw():
            self._refresh_canvas()

    def rotate_180(self) -> None:
        document = self._workspace.canvas().document()
        if document.rotate_180():
            self._refresh_canvas()

    # ---- internals ------------------------------------------------------

    def _refresh_canvas(self) -> None:
        canvas = self._workspace.canvas()
        canvas.document().invalidate_composite()
        canvas.update()
