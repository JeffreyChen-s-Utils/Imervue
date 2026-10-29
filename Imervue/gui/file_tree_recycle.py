"""Hide and restore folders retained in the application recycle bin."""

from __future__ import annotations

from pathlib import Path
from Imervue.multi_language.language_wrapper import language_wrapper


def refresh_pending_hidden(self) -> None:
    """Hide rows for folders pending soft-deletion; un-hide the rest."""
    from Imervue.gui.recycle_bin_dialog import pending_external_paths

    viewer = getattr(self._main_window, "viewer", None)
    pending = pending_external_paths(getattr(viewer, "undo_stack", None) or [])
    model = self.model()
    if model is None:
        return
    for path in self._hidden_paths - pending:
        self._set_row_hidden(model, path, hidden=False)
    for path in pending:
        self._set_row_hidden(model, path, hidden=True)
    self._hidden_paths = set(pending)
    if self._recursive_search is not None:
        self._recursive_search.exclude_hidden()


def _set_row_hidden(self, model, path: str, *, hidden: bool) -> None:
    index = model.index(path)
    if index.isValid():
        self.setRowHidden(index.row(), index.parent(), hidden)


def _soft_delete_folder(self, path: str, notify: bool = True, *, refresh: bool = True) -> None:
    """Hide *path* pending deletion. ``refresh=False`` lets a batch
    caller re-sync the hidden rows once instead of once per folder."""
    viewer = self._main_window.viewer
    viewer.undo_stack.append(
        {
            "mode": "delete_external",
            "deleted_paths": [path],
            "restored": False,
        }
    )
    if refresh:
        self.refresh_pending_hidden()
    if notify and hasattr(self._main_window, "toast"):
        lang = language_wrapper.language_word_dict
        self._main_window.toast.info(
            lang.get("tree_recycled", "Moved to Recycle Bin: {name}").format(
                name=Path(path).name,
            ),
        )
