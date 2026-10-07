"""Native Paint file commands: save a specified tab, save all, and open safely."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from Imervue.gui.file_filters import translated_filter
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import document_io, recent_files
from Imervue.paint.document_status import document_status, refresh_document_status


def native_filter() -> str:
    """Build the native document picker filter using the current UI language."""
    return translated_filter("file_filter_imervue_document", "Imervue document", ("imervue",))


def native_path(path: str) -> str:
    """Append the native suffix instead of overwriting a differently typed source file."""
    if Path(path).suffix.lower() == document_io.FILE_EXTENSION:
        return path
    return path + document_io.FILE_EXTENSION


class DocumentFiles:
    """Reuse the file-menu bridge's notices while preserving per-tab save targets."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.workspace = bridge._workspace

    def save(self, canvas=None, *, save_as: bool = False, reserved: set[str] | None = None) -> bool:
        """Save one editable native document; cancellation/failure leaves it open and dirty."""
        canvas = self.workspace.canvas() if canvas is None else canvas
        state = document_status(canvas)
        if state.document.shape is None:
            return False
        path = state.saved_path if state.saved_format == "imervue" and not save_as else ""
        if not path:
            title = language_wrapper.language_word_dict.get(
                "paint_file_save_document", "Save Document…",
            )
            tabs = getattr(self.workspace, "_tabs", None)
            index = tabs.indexOf(canvas) if tabs is not None else -1
            name = tabs.tabText(index).rstrip(" *") if index >= 0 else "Untitled"
            path, _ = QFileDialog.getSaveFileName(
                self.workspace, f"{title} — {name}", name + ".imervue", native_filter(),
            )
            if not path:
                return False
        path = native_path(path)
        key = os.path.normcase(os.path.realpath(path))
        if reserved is not None and key in reserved:
            self.bridge._warn("paint_file_save_document", language_wrapper.language_word_dict.get(
                "paint_document_duplicate_target", "Another open document uses this save location",
            ))
            return False
        try:
            document_io.save_document(state.document, path)
        except (OSError, ValueError, MemoryError) as exc:
            self.bridge._warn("paint_file_save_document", exc)
            return False
        state.saved_path, state.saved_format = path, "imervue"
        if reserved is not None:
            reserved.add(key)
        self.workspace._set_tab_dirty(canvas, False)
        self._name_tab(canvas, path)
        refresh_document_status(self.workspace, canvas)
        self.bridge._notify_success("paint_file_save_document", "Saved document", path)
        return True

    def save_all(self) -> bool:
        """Save dirty tabs in tab order; stop on the first cancellation or failure."""
        tabs = self.workspace._tabs
        canvases = [tabs.widget(i) for i in range(tabs.count())]
        dirty = self.workspace._tab_dirty
        reserved = {os.path.normcase(os.path.realpath(document_status(c).saved_path))
                    for c in canvases if not dirty.get(c, False) and document_status(c).saved_path}
        for canvas in canvases:
            if dirty.get(canvas, False) and not self.save(canvas, reserved=reserved):
                return False
        return True

    def open(self, path: str = "") -> bool:
        """Decode before creating a tab, preserving every existing document on failure."""
        if not path:
            title = language_wrapper.language_word_dict.get(
                "paint_file_open_document", "Open Document…",
            )
            path, _ = QFileDialog.getOpenFileName(self.workspace, title, "", native_filter())
        if not path:
            return False
        try:
            document = document_io.load_document(path)
        except (OSError, ValueError, MemoryError) as exc:
            self.bridge._warn("paint_file_open_document", exc)
            return False
        canvas = self.workspace.new_tab(width=1, height=1)
        canvas.set_document(document)
        state = document_status(canvas)
        state.source = state.saved_path = str(path)
        state.saved_format = "imervue"
        self.workspace._set_tab_dirty(canvas, False)
        self.workspace._ensure_undo_stack()
        dock = getattr(self.workspace, "_layer_dock", None)
        if dock is not None:
            dock.set_document(document)
        self._name_tab(canvas, path)
        refresh_document_status(self.workspace, canvas)
        recent_files.add(str(path))
        self.bridge.refresh_recent_menu()
        return True

    def _name_tab(self, canvas, path: str) -> None:
        tabs = getattr(self.workspace, "_tabs", None)
        index = tabs.indexOf(canvas) if tabs is not None else -1
        if index >= 0:
            tabs.setTabText(index, Path(path).name)
