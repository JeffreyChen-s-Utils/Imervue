"""Shared "Modify" actions widget.

Both the Deep Zoom menu-bar Modify menu and the right-click context menu
embed this widget (via ``QWidgetAction``) so they expose the exact same
set of editing operations — Develop / Annotate / Rotate CW / Rotate CCW /
Flip H / Flip V / Reset — and stay in sync automatically when any new
operation is added.

The widget only speaks to ``GPUImageView``; it doesn't know anything
about menus, which keeps it trivially reusable from other UIs (dock
panel, toolbar, hotkey palette, etc.).
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget,
)

from Imervue.gui.annotation_dialog import open_annotation_for_path
from Imervue.gpu_image_view.actions.keyboard_actions import rotate_current_image
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class ModifyActionsWidget(QWidget):
    """Compact 3-column grid of edit actions for the current Deep Zoom image.

    Parameters
    ----------
    main_gui:
        The ``GPUImageView`` instance whose current image will be acted on.
    parent:
        Usual Qt parent.
    on_triggered:
        Optional zero-arg callback fired after any button is clicked.
        Menus that embed the widget use this to close themselves so the
        button press feels like a regular menu action.
    """

    action_triggered = Signal()

    def __init__(
        self,
        main_gui: GPUImageView,
        parent: QWidget | None = None,
        on_triggered: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_gui = main_gui
        self._on_triggered = on_triggered

        lang = language_wrapper.language_word_dict

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        title = QLabel(lang.get("modify_menu_title", "Modify"), self)
        title_f = title.font()
        title_f.setBold(True)
        title.setFont(title_f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)

        # (i18n key, fallback label, glyph, handler)
        buttons: list[tuple[str, str, str, Callable[[], None]]] = [
            ("modify_menu_develop",    "Develop",       "🎛",
                self._do_develop),
            ("modify_menu_annotate",   "Annotate",      "✎",
                self._do_annotate),
            ("modify_menu_rotate_cw",  "Rotate CW",     "↻",
                lambda: self._do_rotate(True)),
            ("modify_menu_rotate_ccw", "Rotate CCW",    "↺",
                lambda: self._do_rotate(False)),
            ("modify_menu_flip_h",     "Flip H",        "⇆",
                lambda: self._do_flip("h")),
            ("modify_menu_flip_v",     "Flip V",        "⇅",
                lambda: self._do_flip("v")),
            ("modify_menu_reset",      "Reset",         "⟲",
                self._do_reset),
        ]

        for idx, (key, fallback, glyph, handler) in enumerate(buttons):
            btn = QToolButton(self)
            label = lang.get(key, fallback)
            # Strip trailing "..." that looks OK in menus but clutters a grid.
            if label.endswith("..."):
                label = label[:-3]
            btn.setText(f"{glyph}\n{label}")
            btn.setToolTip(lang.get(key, fallback))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFixedSize(84, 52)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(self._wrap(handler))
            row, col = divmod(idx, 3)
            grid.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        root.addLayout(grid)

    # ------------------------------------------------------------------
    # Wrapping
    # ------------------------------------------------------------------

    def _wrap(self, handler: Callable[[], None]) -> Callable[[], None]:
        def _run() -> None:
            try:
                handler()
            finally:
                self.action_triggered.emit()
                if self._on_triggered is not None:
                    self._on_triggered()
        return _run

    # ------------------------------------------------------------------
    # Current-path helper (same semantics as modify_menu._current_path)
    # ------------------------------------------------------------------

    def _current_path(self) -> str | None:
        viewer = self._main_gui
        images = viewer.model.images
        if not images:
            return None
        if not viewer.deep_zoom:
            return None
        if 0 <= viewer.current_index < len(images):
            return images[viewer.current_index]
        return None

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _do_develop(self) -> None:
        if self._current_path() is None:
            return
        self._main_gui.open_develop_panel()

    def _do_annotate(self) -> None:
        path = self._current_path()
        if not path:
            return
        open_annotation_for_path(self._main_gui, path)

    def _do_rotate(self, clockwise: bool) -> None:
        if self._current_path() is None:
            return
        rotate_current_image(self._main_gui, clockwise=clockwise)

    def _do_flip(self, axis: str) -> None:
        path = self._current_path()
        if not path:
            return

        from Imervue.image.recipe import Recipe
        from Imervue.image.recipe_store import recipe_store
        from Imervue.gpu_image_view.actions.recipe_commands import EditRecipeCommand

        old = recipe_store.get_for_path(path) or Recipe()
        new = Recipe.from_dict(old.to_dict())
        if axis == "h":
            new.flip_h = not new.flip_h
            text = "Flip horizontal"
        else:
            new.flip_v = not new.flip_v
            text = "Flip vertical"

        cmd = EditRecipeCommand(self._main_gui, path, old, new, text=text)
        self._main_gui.undo_manager.push(cmd)

    def _do_reset(self) -> None:
        path = self._current_path()
        if not path:
            return

        from Imervue.image.recipe import Recipe
        from Imervue.image.recipe_store import recipe_store
        from Imervue.gpu_image_view.actions.recipe_commands import EditRecipeCommand

        old = recipe_store.get_for_path(path) or Recipe()
        new = Recipe()
        if old.to_dict() == new.to_dict():
            return
        cmd = EditRecipeCommand(
            self._main_gui, path, old, new, text="Reset edits"
        )
        self._main_gui.undo_manager.push(cmd)
