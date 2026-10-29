"""Crash-recovery prompts and restores for the Paint workspace.

Split out of :mod:`workspace_autosave`; :class:`AutosaveRecoveryMixin` is a base of
:class:`Imervue.paint.workspace_autosave.AutosaveMixin`. It lists pending snapshots,
reopens each recovered document in a new dirty tab, claims that document's files
without stealing another tab's, and offers recovery on startup.
"""
from __future__ import annotations

import logging
import uuid

from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue")


class AutosaveRecoveryMixin:
    """Pending-snapshot listing, restore into new tabs and the recovery prompt."""

    def pending_autosaves(self, *, target_dir=None):
        """Return non-stale recovery candidates for ``target_dir``.

        Thin pass-through over :func:`auto_save.pending_recovery_snapshots`
        so the recovery prompt UI can call into the workspace without
        importing the autosave module directly.
        """
        from Imervue.paint.auto_save import pending_recovery_snapshots
        target = (target_dir if target_dir is not None
                  else getattr(self, "_autosave_target_dir", None))
        return pending_recovery_snapshots(target)

    def restore_snapshot(self, snapshot) -> bool:
        """Install ``snapshot``'s document on the canvas.

        Uses a new tab and :meth:`PaintCanvas.set_document` so layers, masks, vector
        layers, and selections all survive the restore. Returns
        ``False`` when the bundle is unreadable; ``True`` on success.
        """
        from Imervue.paint.auto_save import recover_snapshot
        try:
            document = recover_snapshot(snapshot)
        except (OSError, ValueError) as exc:
            logger.warning("Could not recover Paint autosave %s: %s", snapshot.bundle_path, exc)
            return False
        # Recovery opens a new document; it must never replace unsaved work.
        canvas = self.new_tab(width=1, height=1)
        canvas.set_document(document)
        records = getattr(self, "_autosave_records", None)
        if records is None:
            records = self._autosave_records = {}
        records[canvas] = (document, uuid.uuid4().hex)
        self._claim_recovery_snapshots(snapshot, canvas)
        self._set_tab_dirty(canvas, True)
        if hasattr(self, "_ensure_undo_stack"):
            self._ensure_undo_stack()
        tabs = getattr(self, "_tabs", None)
        if tabs is not None:
            index = tabs.indexOf(canvas)
            tabs.setTabText(index, snapshot.project_name + " *")
            self._refresh_tab_title(canvas)
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(document)
        return True

    def _claim_recovery_snapshots(self, snapshot, canvas) -> None:
        """Own recovered files without stealing another open tab's snapshots."""
        from Imervue.paint.auto_save import list_snapshots
        paths = self._autosave_paths_for(canvas)
        owned = set().union(*self._autosave_paths_by_canvas.values())
        key = self._recovery_key(snapshot)
        candidates = list_snapshots(snapshot.bundle_path.parent)
        paths.update(s.bundle_path for s in candidates
                     if self._recovery_key(s) == key and s.bundle_path not in owned)
        written = getattr(self, "_autosave_written", None)
        if written is None:
            written = self._autosave_written = set()
        written.update(paths)

    @staticmethod
    def _recovery_key(snapshot) -> str:
        return snapshot.document_id or snapshot.source_hint or snapshot.project_name

    def restore_all_autosaves(self, *, target_dir=None) -> int:
        """Recover each document's latest readable state in its own new tab."""
        snapshots = self.pending_autosaves(target_dir=target_dir)
        recovered = getattr(self, "_autosave_recovered", None)
        if recovered is None:
            recovered = self._autosave_recovered = set()
        count = 0
        for snapshot in snapshots:
            key = self._recovery_key(snapshot)
            if key in recovered or not self.restore_snapshot(snapshot):
                continue
            recovered.add(key)
            count += 1
        return count

    def restore_latest_autosave(self, *, target_dir=None) -> bool:
        """Load the most-recent recovery snapshot onto the canvas.

        Returns ``True`` when a snapshot was found and installed; the
        caller drives the user-visible "restore?" prompt around this.
        """
        snapshots = self.pending_autosaves(target_dir=target_dir)
        if not snapshots:
            return False
        return self.restore_snapshot(snapshots[0])

    def _maybe_offer_autosave_recovery(self) -> None:
        """Probe the autosave directory and prompt if anything is there.

        Pulled out as a method so a unit test can stub the snapshot
        list (instead of writing real bundles to ``~``) and verify
        the prompt routing. The prompt itself is a non-blocking
        toast — users in a hurry can ignore it; users who lost
        work can act on it via the recovery dialog.
        """
        try:
            snapshots = self.pending_autosaves()
        except (OSError, ValueError):
            return
        if not snapshots:
            return
        toast = getattr(self, "toast", None)
        lang = language_wrapper.language_word_dict
        msg = lang.get(
            "paint_autosave_recovery_available",
            "{n} autosave snapshot(s) available — File ▸ Restore Autosave",
        ).format(n=len(snapshots))
        if toast is not None:
            toast.warning(msg, duration_ms=6000)
            return
        status = getattr(self, "_status", None)
        if status is not None:
            status.showMessage(msg, 6000)
