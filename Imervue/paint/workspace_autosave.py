"""Autosave / crash-recovery behaviour for the Paint workspace.

Extracted from :mod:`paint_workspace` so the workspace stays under the
file-length budget. :class:`AutosaveMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`; it owns the
periodic snapshot timer, explicit snapshots and failure reporting, and
inherits the background save queue (:mod:`workspace_autosave_queue`),
recovery prompt (:mod:`workspace_autosave_recovery`) and owned-file
cleanup (:mod:`workspace_autosave_files`).
The timer is reused; application-owned workers survive canvas/workspace
destruction long enough to discard cancelled late snapshots.
"""
from __future__ import annotations

import logging
import time
import uuid

from PySide6.QtCore import QTimer

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.document_status import document_status, refresh_document_status
from Imervue.paint.workspace_autosave_files import AutosaveFilesMixin
from Imervue.paint.workspace_autosave_queue import AutosaveQueueMixin
from Imervue.paint.workspace_autosave_recovery import AutosaveRecoveryMixin

logger = logging.getLogger("Imervue")


class AutosaveMixin(AutosaveQueueMixin, AutosaveRecoveryMixin, AutosaveFilesMixin):
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
        except (OSError, ValueError, RuntimeError, MemoryError) as exc:
            # RuntimeError: the canvas's C++ object was deleted between this timer
            # tick being queued and firing (the window closed / a tab torn down).
            AutosaveMixin._report_autosave_error(
                self, str(exc) or type(exc).__name__, canvas=canvas,
            )
            return None
        if snapshot is None:
            return None
        self._record_autosave_success(canvas, snapshot)
        return snapshot.bundle_path

    def _record_autosave_success(self, canvas, snapshot) -> None:
        """Record owned files and UI timestamps for either an explicit or periodic save."""
        last = time.monotonic()
        state = document_status(canvas)
        state.autosave, state.autosave_error, state.autosave_at = "saved", "", last
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
        refresh_document_status(self, canvas)

    def _autosave_record(self, canvas):
        """Return a stable identity for this canvas's current document."""
        records = getattr(self, "_autosave_records", None)
        if records is None:
            records = self._autosave_records = {}
        document = canvas.document()
        record = records.get(canvas)
        if record is None or record[0] is not document:
            jobs = getattr(self, "_autosave_jobs", None)
            if jobs is not None and record is not None:
                jobs.cancel(record[1])
            record = records[canvas] = (document, uuid.uuid4().hex)
            getattr(self, "_autosave_last_by_canvas", {}).pop(canvas, None)
        return record

    def _autosave_title(self, canvas) -> str:
        tabs = getattr(self, "_tabs", None)
        index = tabs.indexOf(canvas) if tabs is not None else -1
        return tabs.tabText(index).rstrip(" *") if index >= 0 else "Untitled"

    def _report_autosave_error(self, message: str, *, canvas=None) -> None:
        logger.warning("Paint autosave failed: %s", message)
        if canvas is not None:
            try:
                state = document_status(canvas)
                state.autosave, state.autosave_error = "failed", message
                refresh_document_status(self, canvas)
            except RuntimeError as exc:
                logger.debug("Autosave status canvas already deleted: %s", exc)
        toast = getattr(self, "toast", None)
        if toast is not None:
            toast.warning(language_wrapper.language_word_dict.get(
                "paint_autosave_failed", "Autosave failed: {error}",
            ).format(error=message))
