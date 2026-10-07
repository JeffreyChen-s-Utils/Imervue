"""Autosave / crash-recovery behaviour for the Paint workspace.

Extracted from :mod:`paint_workspace` so the workspace stays under the
file-length budget. :class:`AutosaveMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`; it owns the
periodic snapshot timer and the recovery prompt. All Qt-resource
lifetimes (the ``QTimer``) are created lazily and reused, matching the
pre-refactor behaviour exactly.
"""
from __future__ import annotations

import logging
import time
import uuid

from PySide6.QtCore import QTimer

from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue")


class AutosaveMixin:
    """Periodic document-snapshot timer + crash-recovery prompt.

    Expects the host to provide ``_canvas`` and ``_status`` attributes
    and a ``toast`` manager, plus a ``_refresh_status_line`` method and
    a ``_last_autosave_at`` slot.
    """

    def start_autosave(
        self, *, interval_sec: int | None = None, target_dir=None,
    ) -> None:
        """Start the periodic snapshot timer.

        Cheap to call repeatedly — a second call replaces the existing
        timer interval rather than stacking timers. Pulled out as an
        explicit method (not ctor wiring) so tests can opt out and
        keep workspace construction cheap.
        """
        from Imervue.paint.auto_save import DEFAULT_INTERVAL_SEC
        seconds = int(interval_sec or DEFAULT_INTERVAL_SEC)
        self._autosave_target_dir = target_dir
        if not hasattr(self, "_autosave_timer"):
            self._autosave_timer = QTimer(self)
            self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self._autosave_timer.start(max(1000, seconds * 1000))

    def stop_autosave(self) -> None:
        if hasattr(self, "_autosave_timer"):
            self._autosave_timer.stop()

    def take_autosave_snapshot_now(self, *, canvas=None):
        """Force an immediate document snapshot.

        Writes the full :class:`PaintDocument` (layers, masks, vectors,
        animation) through :mod:`auto_save` so a crash restore brings
        back the project — not just a flat composite. Returns the
        bundle path or ``None`` if there is nothing to save (empty
        document) or the write failed. On success records the wall-
        clock timestamp so the status line can render
        "Last autosaved Xs ago" — that hint is what tells the user
        their work is captured even when no file has been picked.
        """
        from Imervue.paint.auto_save import write_snapshot
        canvas = self._canvas if canvas is None else canvas
        target = getattr(self, "_autosave_target_dir", None)
        try:
            document = canvas.document()
            record = self._autosave_record(canvas)
            title = self._autosave_title(canvas)
            snapshot = write_snapshot(document, directory=target,
                                      document_id=record[1], project_name=title)
        except (OSError, ValueError, RuntimeError) as exc:
            # RuntimeError: the canvas's C++ object was deleted between this timer
            # tick being queued and firing (the window closed / a tab torn down).
            logger.warning("Paint autosave failed: %s", exc)
            toast = getattr(self, "toast", None)
            if toast is not None:
                toast.warning(language_wrapper.language_word_dict.get(
                    "paint_autosave_failed", "Autosave failed: {error}",
                ).format(error=exc))
            return None
        if snapshot is None:
            return None
        last = time.monotonic()
        stamps = getattr(self, "_autosave_last_by_canvas", None)
        if stamps is None:
            stamps = self._autosave_last_by_canvas = {}
        stamps[canvas] = last
        if canvas is self._canvas:
            self._last_autosave_at = last
        written = getattr(self, "_autosave_written", None)
        if written is None:
            written = self._autosave_written = set()
        written.add(snapshot.bundle_path)
        self._autosave_paths_for(canvas).add(snapshot.bundle_path)
        self._refresh_status_line()
        return snapshot.bundle_path

    def _autosave_record(self, canvas):
        """Return a stable identity for this canvas's current document."""
        records = getattr(self, "_autosave_records", None)
        if records is None:
            records = self._autosave_records = {}
        document = canvas.document()
        record = records.get(canvas)
        if record is None or record[0] is not document:
            record = records[canvas] = (document, uuid.uuid4().hex)
            getattr(self, "_autosave_last_by_canvas", {}).pop(canvas, None)
        return record

    def _autosave_title(self, canvas) -> str:
        tabs = getattr(self, "_tabs", None)
        index = tabs.indexOf(canvas) if tabs is not None else -1
        return tabs.tabText(index).rstrip(" *") if index >= 0 else "Untitled"

    def discard_canvas_autosaves(self, canvas) -> int:
        """Release one closed tab's snapshots and tracking, leaving others alone."""
        getattr(self, "_autosave_records", {}).pop(canvas, None)
        getattr(self, "_autosave_last_by_canvas", {}).pop(canvas, None)
        paths = getattr(self, "_autosave_paths_by_canvas", {}).pop(canvas, set())
        return self._discard_autosave_paths(paths)

    def _autosave_paths_for(self, canvas) -> set:
        paths = getattr(self, "_autosave_paths_by_canvas", None)
        if paths is None:
            paths = self._autosave_paths_by_canvas = {}
        return paths.setdefault(canvas, set())

    def _discard_autosave_paths(self, paths) -> int:
        """Delete recorded paths even when recovery used a different directory."""
        from Imervue.paint.auto_save import AUTOSAVE_META_SUFFIX, AutoSaveSnapshot, discard_snapshot
        written = getattr(self, "_autosave_written", set())
        gone = 0
        for path in list(paths):
            snapshot = AutoSaveSnapshot(path, path.with_suffix(AUTOSAVE_META_SUFFIX), 0.0, "", "")
            try:
                gone += int(discard_snapshot(snapshot))
                written.discard(path)
            except OSError as exc:
                logger.warning("Could not remove Paint autosave: %s", exc)
        return gone

    def discard_own_autosaves(self) -> int:
        """Delete the snapshots this workspace wrote; returns how many went.

        Called once the user has closed with nothing left to lose (saved, or
        chose to discard), so the next launch doesn't offer to recover them.
        Another window's snapshots in the same folder are left alone.
        """
        written = getattr(self, "_autosave_written", None) or set()
        return self._discard_autosave_paths(written)

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

    def _on_autosave_tick(self) -> None:
        """Snapshot every dirty document without changing the active tab.

        An untouched canvas (the viewer's picture loaded into Paint) is nothing to
        recover; snapshotting it would offer a recovery on every launch.
        """
        for canvas, dirty in list(getattr(self, "_tab_dirty", {}).items()):
            if not dirty:
                continue
            if canvas is self._canvas:
                self.take_autosave_snapshot_now()
            else:
                self.take_autosave_snapshot_now(canvas=canvas)

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
