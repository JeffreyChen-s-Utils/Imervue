"""Events dialog — list time-gap photo groups and open one into the grid."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QVBoxLayout, QWidget

from Imervue.library.events import build_events
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class EventsDialog(QDialog):
    """Show events (date-span groups); double-click to load one into the grid."""

    def __init__(self, main_gui: GPUImageView, paths: list[str],
                 parent: QWidget | None = None):
        super().__init__(main_gui if isinstance(main_gui, QWidget) else parent)
        self._main_gui = main_gui
        self._events = build_events(paths)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("events_title", "Events"))
        self.resize(360, 420)

        layout = QVBoxLayout(self)
        if not self._events:
            layout.addWidget(QLabel(lang.get("events_empty", "No dated photos found")))
            return
        self._list = QListWidget()
        for label, group in self._events:
            self._list.addItem(f"{label}  ({len(group)})")
        self._list.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self._list)

    def _open_selected(self, item) -> None:  # pragma: no cover - Qt UI
        row = self._list.row(item)
        if not (0 <= row < len(self._events)):
            return
        _label, group = self._events[row]
        self._main_gui._unfiltered_images = list(group)
        self._main_gui.clear_tile_grid()
        self._main_gui.load_tile_grid_async(group)
        self.accept()


def open_events(main_gui: GPUImageView) -> None:  # pragma: no cover - Qt UI
    paths = list(main_gui.selected_tiles) or list(main_gui.model.images)
    EventsDialog(main_gui, paths).exec()
