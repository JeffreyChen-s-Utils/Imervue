"""Coalesced background Paint saves with immutable inputs and application-owned signals."""
from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from Imervue.paint.auto_save import AutoSaveSnapshot, discard_snapshot, write_snapshot
from Imervue.paint.document import PaintDocument

logger = logging.getLogger("Imervue.paint.autosave")


@dataclass(frozen=True)
class OwnedContent:
    """An already detached document; only its background writer may read its arrays."""

    document: PaintDocument

    def materialize(self) -> PaintDocument:
        """Transfer the private document to the writer without another array copy."""
        return self.document


@dataclass(frozen=True)
class SaveRequest:
    """One coherent document version and its stable recovery identity."""

    document_id: str
    content: object
    directory: object = None
    title: str = "Untitled"
    cancelled: Event = field(default_factory=Event, compare=False)


class _Signals(QObject):
    finished = Signal(object, object, str)


class _SaveJob(QRunnable):
    def __init__(self, request: SaveRequest) -> None:
        super().__init__()
        self.request = request
        self.signals = _Signals(QApplication.instance())

    def run(self) -> None:
        snapshot, message = None, ""
        try:
            if self.request.cancelled.is_set():
                return
            document = self.request.content.materialize()
            if self.request.cancelled.is_set():
                return
            snapshot = write_snapshot(
                document, directory=self.request.directory,
                document_id=self.request.document_id, project_name=self.request.title,
            )
            if snapshot is not None and self.request.cancelled.is_set():
                discard_snapshot(snapshot)
                snapshot = None
        except Exception as exc:  # worker boundary must always return its terminal packet
            logger.exception("Paint background autosave failed")
            message = str(exc) or type(exc).__name__
        finally:
            self.signals.finished.emit(self, snapshot, message)


class AutosaveJobs(QObject):
    """One writer and one latest pending version per document, with nonblocking retirement."""

    saved = Signal(str, object, str)

    def __init__(self, owner: QObject, *, pool: QThreadPool | None = None) -> None:
        super().__init__(QApplication.instance())
        self._pool = pool or QThreadPool.globalInstance()
        self._pending: OrderedDict[str, SaveRequest] = OrderedDict()
        self._active: _SaveJob | None = None
        self._closed = False
        owner.destroyed.connect(self.close)

    def request(self, request: SaveRequest) -> None:
        """Coalesce duplicates and replace unstarted versions without touching the live document."""
        if self._closed:
            return
        if (self._active is not None
                and not self._active.request.cancelled.is_set()
                and self._active.request.document_id == request.document_id
                and self._active.request.content is request.content
                and self._active.request.directory == request.directory
                and self._active.request.title == request.title):
            self._pending.pop(request.document_id, None)
            return
        self._pending[request.document_id] = request
        self._start_next()

    def cancel(self, document_id: str) -> None:
        """Forget one document; an executing writer deletes its late result after completion."""
        self._pending.pop(document_id, None)
        if self._active is not None and self._active.request.document_id == document_id:
            self._active.request.cancelled.set()

    def cancel_all(self) -> None:
        """Cancel pending/executing saves without waiting for compression or disk I/O."""
        self._pending.clear()
        if self._active is not None:
            self._active.request.cancelled.set()

    def discard_result(self, snapshot: AutoSaveSnapshot) -> None:
        """Delete an obsolete completed result off the UI thread."""
        self._pool.start(_DiscardJob(snapshot))

    @Slot()
    def close(self) -> None:
        """Retire the owner while retaining the writer/sender until its queued terminal signal."""
        self._closed = True
        self.cancel_all()
        if self._active is None:
            self.deleteLater()

    def _start_next(self) -> None:
        if self._closed or self._active is not None or not self._pending:
            return
        _, request = self._pending.popitem(last=False)
        job = self._active = _SaveJob(request)
        job.signals.finished.connect(self._done, Qt.ConnectionType.QueuedConnection)
        self._pool.start(job)

    @Slot(object, object, str)
    def _done(self, job, snapshot: AutoSaveSnapshot | None, message: str) -> None:
        job.signals.deleteLater()
        if self._active is not job:
            return
        self._active = None
        # Cancellation can arrive after the worker's final check but before UI
        # delivery. Finish deleting on another job, never disk I/O in this slot.
        if job.request.cancelled.is_set():
            if snapshot is not None:
                self.discard_result(snapshot)
        elif not self._closed:
            self.saved.emit(job.request.document_id, snapshot, message)
        self._start_next()
        if self._closed:
            self.deleteLater()


class _DiscardJob(QRunnable):
    def __init__(self, snapshot: AutoSaveSnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot

    def run(self) -> None:
        try:
            discard_snapshot(self._snapshot)
        except OSError as exc:
            logger.warning("Could not discard late Paint autosave: %s", exc)
