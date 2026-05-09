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
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
        bottom.addWidget(clear_btn)
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
        """Rebuild the grid from the current state's color_history."""
        self._clear_grid()
        history = self._state.color_history
        for index, rgb in enumerate(history):
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

    # ---- internals -------------------------------------------------------

    def _on_state_event(self, channel: str) -> None:
        from Imervue.paint.tool_state import EVENT_HISTORY
        if channel == EVENT_HISTORY:
            self.refresh()

    def _on_swatch_clicked(self, rgb: tuple[int, int, int]) -> None:
        self._state.set_foreground(rgb, commit=False)
        self.color_chosen.emit(int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def _on_clear(self) -> None:
        self._state.color_history.clear()
        self._state._emit("color_history")  # noqa: SLF001
        self.refresh()

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
        btn.setToolTip(f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
        # Right-click → remove from history.
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda *_, c=rgb: self._on_swatch_remove_requested(c),
        )
        return btn

    def _on_swatch_remove_requested(self, rgb: tuple[int, int, int]) -> None:
        history = list(self._state.color_history)
        if rgb in history:
            self.remove_at(history.index(rgb))
