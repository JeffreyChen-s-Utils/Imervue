"""Floating swatch panel — recent colours + drag-to-reorder.

The :class:`Imervue.paint.tool_state.ToolState` already tracks a
``color_history`` list of recently-committed foreground colours.
This module wraps that list in a free-floating dock so the user can
keep their last N colours one click away regardless of which tab
the colour dock is on.

The dock body shows a 6-column grid of swatches (each 24×24 px) plus
a "Clear history" button at the bottom. Clicking a swatch sets the
foreground; right-clicking removes that swatch from the list. The
list also supports drag-to-reorder via :meth:`reorder` so frequently-
used colours can be pinned at the front.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui.dialog_rows import confirm
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

_SWATCH_PX = 24
_SWATCH_COLUMNS = 6


class SwatchPanel(QDockWidget):
    """Recent-colour grid bound to a :class:`ToolState`.

    The panel auto-refreshes when the state's history channel fires
    so any committed colour change in the workspace updates the grid
    without explicit re-binding.
    """

    color_chosen = Signal(int, int, int)   # (r, g, b)

    def __init__(self, state: ToolState, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_swatches", "Swatches"), parent)

        self._state = state

        body = QWidget()
        layout = QVBoxLayout(body)

        self._palette_box = QComboBox()
        self._palette_box.setToolTip(lang.get(
            "paint_swatch_palette_tooltip",
            "Show your recent colours or one of the palettes",
        ))
        self._palette_box.currentIndexChanged.connect(self._on_palette_chosen)
        layout.addWidget(self._palette_box)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(2)
        layout.addWidget(self._grid_host)

        bottom = QHBoxLayout()
        clear_btn = QPushButton(lang.get(
            "paint_swatch_clear", "Clear",
        ))
        clear_btn.setToolTip(lang.get(
            "paint_swatch_clear_tooltip",
            "Drop every recent colour from the history — irreversible "
            "but the swatches repopulate as soon as new colours are committed",
        ))
        clear_btn.clicked.connect(self._on_clear)
        self._clear_btn = clear_btn
        bottom.addWidget(clear_btn)
        self._save_palette_btn = QPushButton(
            lang.get("paint_swatch_save_palette", "Save as Palette…"))
        self._save_palette_btn.setToolTip(lang.get(
            "paint_swatch_save_palette_tooltip", "Keep the recent colours as a named palette"))
        self._save_palette_btn.clicked.connect(self._on_save_palette)
        bottom.addWidget(self._save_palette_btn)
        self._delete_palette_btn = QPushButton(
            lang.get("paint_swatch_delete_palette", "Delete Palette"))
        self._delete_palette_btn.clicked.connect(self._on_delete_palette)
        bottom.addWidget(self._delete_palette_btn)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        layout.addStretch(1)
        self.setWidget(body)

        # Floatable + closable + movable (the workspace-default flags
        # already cover this, but a swatch panel is typically pinned
        # *floating* so the artist can stash it on a second monitor).
        self.setFeatures(
            self.features()
            | self.DockWidgetFeature.DockWidgetFloatable
            | self.DockWidgetFeature.DockWidgetClosable
            | self.DockWidgetFeature.DockWidgetMovable,
        )

        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self.refresh()

    # ---- public ----------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the palette list and the grid: the chosen palette, else the recent colours."""
        from Imervue.paint.color_palette import RECENT_COLOURS, is_built_in, palette_colours
        self._fill_palette_box()
        chosen = self._state.swatch_palette
        recent = chosen == RECENT_COLOURS
        self._clear_btn.setEnabled(recent)
        self._save_palette_btn.setEnabled(recent and bool(self._state.color_history))
        self._delete_palette_btn.setEnabled(not recent and not is_built_in(chosen))
        self._clear_grid()
        for index, rgb in enumerate(palette_colours(chosen, self._state.color_history)):
            row, col = divmod(index, _SWATCH_COLUMNS)
            btn = self._make_swatch_button(rgb)
            btn.clicked.connect(
                lambda *_, c=rgb: self._on_swatch_clicked(c),
            )
            self._grid.addWidget(btn, row, col)

    def reorder(self, src: int, dst: int) -> bool:
        """Move the colour at ``src`` to position ``dst`` in the history.

        Used by drag-and-drop in the dock — exposed publicly so
        keyboard shortcuts and tests can drive the same path. Returns
        ``True`` on a real change, ``False`` for noop / out-of-range.
        """
        history = list(self._state.color_history)
        if not 0 <= src < len(history):
            return False
        if not 0 <= dst < len(history):
            return False
        if src == dst:
            return False
        item = history.pop(src)
        history.insert(dst, item)
        # The state's color history is read-only at the API level;
        # rewrite the underlying list and emit the history channel
        # so subscribers refresh.
        self._state.color_history.clear()
        self._state.color_history.extend(history)
        self._state._emit("color_history")  # noqa: SLF001
        self.refresh()
        return True

    def remove_at(self, index: int) -> bool:
        """Remove a single colour from the history."""
        history = list(self._state.color_history)
        if not 0 <= index < len(history):
            return False
        del history[index]
        self._state.color_history.clear()
        self._state.color_history.extend(history)
        self._state._emit("color_history")  # noqa: SLF001
        self.refresh()
        return True

    # ---- palettes ----------------------------------------------------------

    def _fill_palette_box(self) -> None:
        from Imervue.paint.color_palette import RECENT_COLOURS, all_palettes
        lang = language_wrapper.language_word_dict
        box = self._palette_box
        box.blockSignals(True)
        box.clear()
        box.addItem(lang.get("paint_swatch_recent", "Recent colours"), RECENT_COLOURS)
        for palette in all_palettes():
            box.addItem(palette.name, palette.name)
        box.setCurrentIndex(max(0, box.findData(self._state.swatch_palette)))
        box.blockSignals(False)

    def _on_palette_chosen(self, index: int) -> None:
        if index >= 0:
            self._state.set_swatch_palette(self._palette_box.itemData(index))

    def save_recent_as_palette(self, name: str) -> bool:
        """Keep the recent colours as a palette called *name* and show it. False if not saved.

        Refused for an empty name, a name already taken, or no recent colours.
        """
        from Imervue.paint.color_palette import (
            MAX_PALETTE_SIZE,
            Palette,
            all_palettes,
            load_palettes,
            save_palettes,
        )
        name = str(name).strip()
        colours = tuple(tuple(int(c) for c in rgb) for rgb in self._state.color_history)
        if not name or not colours or name in {p.name for p in all_palettes()}:
            return False
        save_palettes([*load_palettes(), Palette(name, colours[:MAX_PALETTE_SIZE])])
        self._state.set_swatch_palette(name)
        self.refresh()
        return True

    def delete_palette(self, name: str) -> bool:
        """Delete your palette *name* (built-in ones stay) and go back to the recent colours."""
        from Imervue.paint.color_palette import (
            RECENT_COLOURS,
            is_built_in,
            load_palettes,
            save_palettes,
        )
        mine = load_palettes()
        if is_built_in(name) or name not in {p.name for p in mine}:
            return False
        save_palettes([p for p in mine if p.name != name])
        self._state.set_swatch_palette(RECENT_COLOURS)
        self.refresh()
        return True

    def _on_save_palette(self) -> None:  # pragma: no cover - Qt dialog
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self, lang.get("paint_swatch_save_palette", "Save as Palette…"),
            lang.get("paint_swatch_palette_name", "Palette name"))
        if ok:
            self.save_recent_as_palette(name)

    def _on_delete_palette(self) -> None:  # pragma: no cover - Qt dialog
        lang = language_wrapper.language_word_dict
        name = self._state.swatch_palette
        if confirm(self, lang.get("paint_swatch_delete_palette", "Delete Palette"),
                   lang.get("paint_swatch_delete_palette_confirm",
                            "Delete the palette “{name}”?").format(name=name)):
            self.delete_palette(name)

    # ---- internals -------------------------------------------------------

    def _on_state_event(self, channel: str) -> None:
        from Imervue.paint.tool_state import EVENT_HISTORY
        if channel == EVENT_HISTORY:
            self.refresh()

    def _on_swatch_clicked(self, rgb: tuple[int, int, int]) -> None:
        self._state.set_foreground(rgb, commit=False)
        self.color_chosen.emit(int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def _on_clear(self) -> None:
        # Clearing wipes the entire colour history — confirm first so
        # a misclick on the small "Clear" button doesn't drop a long
        # session's worth of saved palette colours.
        if self._state.color_history and not self._confirm_clear():
            return
        self._state.color_history.clear()
        self._state._emit("color_history")  # noqa: SLF001
        self.refresh()

    def _confirm_clear(self) -> bool:  # pragma: no cover - Qt UI
        """Ask before wiping the entire swatch history."""
        lang = language_wrapper.language_word_dict
        agreed = confirm(
            self,
            lang.get("paint_swatch_clear", "Clear"),
            lang.get(
                "paint_swatch_clear_confirm",
                "Drop every recent colour from the history? "
                "This cannot be undone.",
            ),
        )
        return agreed

    def _clear_grid(self) -> None:
        while self._grid.count():
            child = self._grid.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _make_swatch_button(self, rgb: tuple[int, int, int]) -> QToolButton:
        btn = QToolButton()
        btn.setFixedSize(_SWATCH_PX, _SWATCH_PX)
        btn.setAutoRaise(False)
        pix = QPixmap(_SWATCH_PX, _SWATCH_PX)
        pix.fill(QColor(*rgb))
        painter = QPainter(pix)
        painter.setPen(QColor(0, 0, 0, 80))
        painter.drawRect(0, 0, _SWATCH_PX - 1, _SWATCH_PX - 1)
        painter.end()
        btn.setIcon(pix)
        btn.setIconSize(pix.size())
        btn.setToolTip(
            f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}  ({rgb[0]},{rgb[1]},{rgb[2]})",
        )
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, c=rgb, b=btn: self._on_swatch_context_menu(c, b, pos),
        )
        return btn

    def _on_swatch_context_menu(
        self, rgb: tuple[int, int, int], button, pos,
    ) -> None:
        """Right-click → small menu with copy / move-to-top / remove
        affordances. Keeps the previous remove behaviour reachable
        without forcing the user to memorise a specific gesture."""
        from PySide6.QtWidgets import QApplication, QMenu
        lang = language_wrapper.language_word_dict
        menu = QMenu(button)
        copy_act = menu.addAction(
            lang.get("paint_swatch_copy_hex", "Copy as #RRGGBB"),
        )
        as_bg_act = menu.addAction(
            lang.get("paint_swatch_set_bg", "Set as Background"),
        )
        move_top_act = menu.addAction(
            lang.get("paint_swatch_move_top", "Move to Front"),
        )
        menu.addSeparator()
        remove_act = menu.addAction(
            lang.get("paint_swatch_remove", "Remove from History"),
        )
        # Reordering and removing change the recent colours, not a palette.
        from Imervue.paint.color_palette import RECENT_COLOURS
        showing_recent = self._state.swatch_palette == RECENT_COLOURS
        move_top_act.setEnabled(showing_recent)
        remove_act.setEnabled(showing_recent)
        chosen = menu.exec(button.mapToGlobal(pos))
        if chosen is copy_act:
            QApplication.clipboard().setText(
                f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}",
            )
        elif chosen is as_bg_act:
            self._state.set_background(rgb)
        elif chosen is move_top_act:
            history = list(self._state.color_history)
            if rgb in history:
                self.reorder(history.index(rgb), 0)
        elif chosen is remove_act:
            history = list(self._state.color_history)
            if rgb in history:
                self.remove_at(history.index(rgb))
