"""Autosave / crash-recovery behaviour for the Paint workspace.

Extracted from :mod:`paint_workspace` so the workspace stays under the
file-length budget. :class:`AutosaveMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`; it owns the
periodic snapshot timer and the recovery prompt. All Qt-resource
lifetimes (the ``QTimer``) are created lazily and reused, matching the
pre-refactor behaviour exactly.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer

from Imervue.multi_language.language_wrapper import language_wrapper


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

    def take_autosave_snapshot_now(self):
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
        import time
        from Imervue.paint.auto_save import write_snapshot
        document = self._canvas.document()
        target = getattr(self, "_autosave_target_dir", None)
        try:
            snapshot = write_snapshot(document, directory=target)
        except (OSError, ValueError):
            return None
        if snapshot is None:
            return None
        self._last_autosave_at = time.monotonic()
        self._refresh_status_line()
        return snapshot.bundle_path

    def pending_autosaves(self, *, target_dir=None):
        """Return non-stale recovery candidates for ``target_dir``.

        Thin pass-through over :func:`auto_save.pending_recovery_snapshots`
        so the recovery prompt UI can call into the workspace without
        importing the autosave module directly.
        """
        from Imervue.paint.auto_save import pending_recovery_snapshots
        return pending_recovery_snapshots(target_dir)

    def restore_snapshot(self, snapshot) -> bool:
        """Install ``snapshot``'s document on the canvas.

        Uses :meth:`PaintCanvas.set_document` so layers, masks, vector
        layers, and selections all survive the restore. Returns
        ``False`` when the bundle is unreadable; ``True`` on success.
        """
        from Imervue.paint.auto_save import recover_snapshot
        try:
            document = recover_snapshot(snapshot)
        except (OSError, ValueError):
            return False
        self._canvas.set_document(document)
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(document)
        return True

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
        self.take_autosave_snapshot_now()

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
            "{n} autosave snapshot(s) available — File ▸ Restore",
        ).format(n=len(snapshots))
        if toast is not None:
            toast.warning(msg, duration_ms=6000)
            return
        status = getattr(self, "_status", None)
        if status is not None:
            status.showMessage(msg, 6000)
