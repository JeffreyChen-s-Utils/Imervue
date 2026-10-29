"""Route deletions among viewer images, retained folders, and OS trash."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from Imervue.gui.file_tree_paths import _partition_delete_batch
from Imervue.gui.file_tree_trash import _TrashRequest


def _delete_paths(self, paths: list[str]) -> None:
    """Send every existing path in *paths* to the trash.

    For a single path this defers to ``_delete_path`` so the existing
    per-file toast is preserved; for a batch the individual toasts are
    suppressed and replaced with one summary so the user isn't spammed.
    Every batch runs its OS-trash calls on a background worker, in
    grouped shell operations — one ``send2trash`` call costs ~0.27 s
    regardless of how few files it carries, so even a handful deleted
    one at a time stalls the GUI for seconds.
    """
    existing = [p for p in paths if Path(p).exists()]
    if not existing:
        return
    if len(existing) == 1:
        self._delete_path(existing[0])
        return
    self._delete_batch_async(existing)


def _delete_batch_async(self, existing: list[str]) -> None:
    """Batch delete: soft-delete in memory, trash on a worker."""
    viewer = self._main_window.viewer
    in_list, folders, loose = _partition_delete_batch(existing, viewer.model.images)
    if in_list:
        self._batch_delete_from_viewer_list(in_list, viewer)
    if folders:
        for folder in folders:
            self._soft_delete_folder(folder, notify=False, refresh=False)
        # One re-sync for the whole batch. refresh_pending_hidden costs
        # a model lookup per pending path, so refreshing inside the loop
        # is quadratic and stalls the tree on a large folder selection.
        self.refresh_pending_hidden()
    if not loose:
        self._notify_deleted_batch(len(existing))
        return
    self._trash_in_background(
        _TrashRequest(
            tuple(loose),
            partial(self._notify_batch_result, len(existing) - len(loose)),
        )
    )


def _delete_path(self, path: str):
    if not Path(path).exists():
        return
    viewer = self._main_window.viewer
    images = viewer.model.images
    if Path(path).is_file() and path in images:
        self._delete_from_viewer_list(path, viewer, images)
    else:
        self._delete_external(path)


def _delete_external(self, path: str) -> None:
    # Folders go through the app Recycle Bin (kept on disk + hidden, sent to
    # the OS trash only at shutdown) so they are restorable in-app; loose
    # non-list files go straight to the OS trash — on the worker, because
    # even a one-file shell call blocks for ~0.27 s, which is a visible
    # hitch every time you press Delete.
    if Path(path).is_dir():
        self._soft_delete_folder(path)
        return
    self._trash_in_background(_TrashRequest((path,), partial(self._notify_single_result, path)))
