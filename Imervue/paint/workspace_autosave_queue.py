"""Background autosave queue for the Paint workspace.

Split out of :mod:`workspace_autosave`; :class:`AutosaveQueueMixin` is a base of
:class:`Imervue.paint.workspace_autosave.AutosaveMixin`. Each timer tick hands every
dirty document's committed history to the application-owned
:class:`Imervue.paint.autosave_jobs.AutosaveJobs` worker, and the delivery slot keeps
only results for documents that are still open.
"""
from __future__ import annotations

import copy
import logging

from PySide6.QtCore import QObject, Qt

from Imervue.paint.document_status import document_status, refresh_document_status

logger = logging.getLogger("Imervue")


class AutosaveQueueMixin:
    """Timer tick, background save requests and late-result delivery."""

    def _on_autosave_tick(self) -> None:
        """Queue each dirty document's latest committed version without changing the active tab.

        An untouched canvas (the viewer's picture loaded into Paint) is nothing to
        recover; snapshotting it would offer a recovery on every launch.
        Non-QObject hosts retain the synchronous adapter for headless callers.
        """
        # A snapshot: saving a tab updates the dirty map.
        for canvas, dirty in tuple(getattr(self, "_tab_dirty", {}).items()):
            if not dirty:
                continue
            if isinstance(self, QObject):
                self._request_autosave(canvas)
            elif canvas is self._canvas:
                self.take_autosave_snapshot_now()
            else:
                self.take_autosave_snapshot_now(canvas=canvas)

    def _request_autosave(self, canvas) -> None:
        """Enqueue committed history in O(1), copying only when no immutable state exists."""
        from Imervue.paint.autosave_jobs import AutosaveJobs, OwnedContent, SaveRequest
        try:
            document = canvas.document()
            record = self._autosave_record(canvas)
            stack = getattr(self, "_undo_stacks", {}).get(canvas)
            content = (stack.available_snapshot if stack is not None
                       and stack.document is document else None)
            if content is None:
                # A document above its history cap still needs recovery. This
                # fallback captures a coherent UI-thread copy; compression and
                # all file writes remain on the worker.
                content = OwnedContent(copy.deepcopy(document))
            jobs = getattr(self, "_autosave_jobs", None)
            if jobs is None:
                jobs = self._autosave_jobs = AutosaveJobs(self)
                # AutosaveJobs._done is a queued UI-thread slot. Record ownership
                # before another UI event can close the tab or discard its files.
                jobs.saved.connect(
                    self._on_async_autosave_saved, Qt.ConnectionType.DirectConnection,
                )
            jobs.request(SaveRequest(record[1], content,
                                     getattr(self, "_autosave_target_dir", None),
                                     self._autosave_title(canvas)))
            state = document_status(canvas)
            state.autosave, state.autosave_error = "pending", ""
            refresh_document_status(self, canvas)
        except (OSError, ValueError, RuntimeError, MemoryError) as exc:
            self._report_autosave_error(str(exc) or type(exc).__name__, canvas=canvas)

    def _on_async_autosave_saved(self, document_id, snapshot, message) -> None:
        record = next(((canvas, record[0]) for canvas, record in
                       getattr(self, "_autosave_records", {}).items()
                       if record[1] == document_id), None)
        current = False
        if record is not None:
            try:
                current = record[0].document() is record[1]
            except RuntimeError as exc:
                logger.debug("Canvas disappeared before autosave delivery: %s", exc)
        if not current:
            if snapshot is not None:
                self._autosave_jobs.discard_result(snapshot)
            return
        if message:
            self._report_autosave_error(message, canvas=record[0])
        if snapshot is not None:
            self._record_autosave_success(record[0], snapshot)
