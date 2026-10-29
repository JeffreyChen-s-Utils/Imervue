"""Refresh loaded directories and filter rows by matching descendants."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QFileSystemModel


def _refresh_tree(self) -> None:
    """Force QFileSystemModel to re-scan the current root.

    The model does not watch the folders it lists (``DontWatchForChanges``:
    a change-notification handle on a folder stops Windows from renaming or
    moving the folders above it), so changes made outside the tree show
    after this runs: on F5 / Refresh, when Imervue comes back to the front,
    and when the open folder changes.
    """
    model: QFileSystemModel = self.model()
    root = self.rootIndex()
    if not root.isValid():
        return
    path = model.filePath(root)
    if path:
        # Re-attempt any folder whose preview is currently missing (it may
        # have just gained an image, or recovered from a mid-delete read).
        clear_missing = getattr(model, "clear_missing_previews", None)
        if callable(clear_missing):
            clear_missing()
        # setRootPath() re-stats the directory even if the value is the same
        model.setRootPath("")
        model.setRootPath(path)
        self.setRootIndex(model.index(path))
        self.apply_search_filter()


def set_search_text(self, text: str) -> None:
    """Filter currently-loaded tree rows by basename substring."""
    self._search_text = text.strip().lower()
    self.apply_search_filter()


def apply_search_filter(self) -> None:
    """Show only rows matching the active search or containing matches."""
    model = self.model()
    if model is None:
        return
    root = self.rootIndex()
    if not self._search_text:
        self._set_subtree_hidden(root, hidden=False)
        self.refresh_pending_hidden()
        return
    self._filter_children(root)
    self.refresh_pending_hidden()


def _set_subtree_hidden(self, parent, *, hidden: bool) -> None:
    model = self.model()
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        self.setRowHidden(row, parent, hidden)
        self._set_subtree_hidden(index, hidden=hidden)


def _filter_children(self, parent) -> bool:
    model = self.model()
    any_visible = False
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        child_visible = self._filter_children(index)
        own_match = self._index_matches_search(index)
        visible = own_match or child_visible
        self.setRowHidden(row, parent, not visible)
        any_visible = any_visible or visible
    return any_visible


def _index_matches_search(self, index) -> bool:
    model = self.model()
    path = ""
    if hasattr(model, "filePath"):
        path = model.filePath(index)
    name = Path(path).name if path else str(index.data() or "")
    return self._search_text in name.lower()
