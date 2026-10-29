"""
重複圖片結果操作
Duplicate-result actions — the dialog's "Select Redundant" and "Delete Selected"
flows, mixed into :class:`DuplicateDetectionDialog`.

Deletes go through ``trash_ops.FileDeleteWorker`` in one batch off the GUI
thread; what the Recycle Bin refuses is offered for permanent deletion.
"""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt

from Imervue.gui.dialog_rows import confirm
from Imervue.gui.trash_failure_notice import offer_permanent_delete
from Imervue.image.dimensions import image_dimensions

logger = logging.getLogger("Imervue.duplicate_detection")

_COUNT_PLACEHOLDER = "{count}"


class DuplicateActionsMixin:
    """Select-redundant and batched delete for the duplicate results tree.

    The host dialog provides ``_tree``, ``_lang``, ``_groups``, the buttons,
    ``_status_label``, ``_pending_delete_items`` and ``_delete_worker``.
    """

    def _delete_selected(self):
        items = self._tree.selectedItems()
        paths = []
        for item in items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                paths.append((item, path))
        if not paths:
            return
        question = self._lang.get(
            "duplicate_confirm_msg", "Move {count} file(s) to trash?",
        ).replace(_COUNT_PLACEHOLDER, str(len(paths)))
        if not confirm(self, self._lang.get("duplicate_confirm_title", "Confirm Delete"), question):
            return
        # 移到垃圾桶是逐檔的 shell 呼叫，大量重複檔在 UI 執行緒跑會凍住
        # 整個視窗 — 交給背景 worker，完成後再更新樹與狀態列。
        from Imervue.system.trash_ops import FileDeleteWorker
        self._delete_btn.setEnabled(False)
        # Disable Scan too: a scan mid-delete clears the tree, destroying the
        # QTreeWidgetItems held in _pending_delete_items, so _on_delete_finished
        # would then touch deleted C++ objects and crash.
        self._scan_btn.setEnabled(False)
        self._select_redundant_btn.setEnabled(False)
        self._pending_delete_items = {path: item for item, path in paths}
        self._delete_worker = FileDeleteWorker([p for _item, p in paths], self)
        self._delete_worker.finished_with.connect(self._on_delete_finished)
        self._delete_worker.start()

    def _on_delete_finished(self, trashed: list, failed: list):
        import contextlib
        pending = getattr(self, "_pending_delete_items", {})
        # What the Recycle Bin could not take (a memory card, a network share)
        # goes for good only if the user says so.
        removed = offer_permanent_delete(self, failed)
        for path in [*trashed, *removed]:
            item = pending.pop(path, None)
            if item is None:
                continue
            # The item's C++ object may already be gone (defensive); a live
            # scan can no longer clear the tree here, but guard anyway.
            with contextlib.suppress(RuntimeError):
                parent = item.parent()
                if parent is not None:
                    parent.removeChild(item)
        for path in failed:
            if path not in removed:
                logger.warning("Failed to delete %s", path)
        self._pending_delete_items = {}
        if self._delete_worker is not None:
            self._delete_worker.deleteLater()
            self._delete_worker = None
        self._delete_btn.setEnabled(True)
        self._scan_btn.setEnabled(True)
        self._select_redundant_btn.setEnabled(True)
        self._status_label.setText(
            self._lang.get("duplicate_deleted", "{count} file(s) deleted").replace(
                _COUNT_PLACEHOLDER, str(len(trashed) + len(removed))
            ))

    def _select_redundant(self):
        """Keep the best image per group (most pixels, then largest file) and
        select the rest, so the user can review before Delete Selected."""
        from Imervue.library.dedupe_resolver import Candidate, plan_discards
        groups = [
            [Candidate(path, *self._probe_dims(path), size) for path, size in group]
            for group in self._groups
        ]
        discards = set(plan_discards(groups))
        self._tree.clearSelection()
        count = self._select_paths(discards)
        self._status_label.setText(
            self._lang.get(
                "duplicate_selected_redundant",
                "{count} redundant file(s) selected — review, then Delete Selected",
            ).replace(_COUNT_PLACEHOLDER, str(count)))

    def _select_paths(self, paths: set[str]) -> int:
        count = 0
        for gi in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(gi)
            for ci in range(group_item.childCount()):
                child = group_item.child(ci)
                if child.data(0, Qt.ItemDataRole.UserRole) in paths:
                    child.setSelected(True)
                    count += 1
        return count

    @staticmethod
    def _probe_dims(path: str) -> tuple[int, int]:
        """Pixel dimensions read from the header; (0, 0) if unreadable."""
        return image_dimensions(path) or (0, 0)
