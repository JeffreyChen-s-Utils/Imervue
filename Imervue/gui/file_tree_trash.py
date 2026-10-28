"""Own queued OS-trash requests, worker completion, and shutdown draining."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from Imervue.gui.trash_failure_notice import offer_permanent_delete
from Imervue.gui.file_tree_feedback import toast
from Imervue.multi_language.language_wrapper import language_wrapper


@dataclass(frozen=True)
class _TrashRequest:
    """One queued OS-trash ask: the paths, and how to report what landed.

    Requests are merged into a single shell call, so each one carries its
    own completion callback — a single-file delete keeps naming its file in
    the toast even when it rides along with someone else's batch.
    """

    paths: tuple[str, ...]
    on_done: Callable[[list[str]], None] = field(repr=False)


def _trash_in_background(self, request: _TrashRequest) -> None:
    """Queue *request* for the OS-trash worker and pump the queue."""
    self._pending_trash.append(request)
    self._pump_trash_queue()


def _pump_trash_queue(self) -> None:
    """Start one worker for everything queued, if none is running.

    Asks that arrive while a worker is in flight wait and go over in the
    next batch. A grouped shell call costs the same ~0.27 s as a
    single-file one, so a burst of Delete presses collapses into one
    round-trip instead of one thread — and none of it on the GUI thread.
    """
    if self._trash_workers or not self._pending_trash:
        return
    from Imervue.system.trash_ops import FileDeleteWorker

    batch, self._pending_trash = self._pending_trash, []
    worker = FileDeleteWorker([path for request in batch for path in request.paths], parent=self)
    worker.progress.connect(self._on_trash_progress)
    worker.finished_with.connect(
        lambda done, failed, w=worker: self._on_trash_finished(w, batch, done, failed),
    )
    self._trash_workers.add(worker)
    worker.start()


def _on_trash_finished(
    self, worker, batch: list[_TrashRequest], done: list[str], failed: list[str]
) -> None:
    self._trash_workers.discard(worker)
    worker.deleteLater()
    # What the Recycle Bin could not take (a memory card, a network share)
    # goes for good only if the user says so.
    landed = set(done) | set(offer_permanent_delete(self, failed))
    for request in batch:
        request.on_done([p for p in request.paths if p in landed])
    still_there = [path for path in failed if path not in landed]
    if still_there:
        lang = language_wrapper.language_word_dict
        toast(
            self,
            "warning",
            lambda: lang.get(
                "tree_delete_failed_count",
                "Couldn't delete {count} item(s)",
            ).format(count=len(still_there)),
        )
    self._pump_trash_queue()


def shutdown(self) -> None:
    """Wait for any in-flight OS-trash workers so their QThreads aren't
    destroyed mid-run when this view (or its owning window) is torn down.

    FileDeleteWorker is parented to this view; without this a secondary
    window closing (which deleteLater's the view) would destroy a running
    worker thread ('QThread: Destroyed while thread is still running'), and
    the primary window's os._exit would abort an in-flight OS-trash batch
    partway. The main window calls this from closeEvent before teardown.
    """
    # The list() copy is load-bearing, not redundant: ``_trash_workers`` is a
    # set, and a worker finishing inside wait() fires _on_trash_finished,
    # which discards it — mutating the set mid-iteration. Do not inline.
    for worker in list(self._trash_workers):  # NOSONAR
        with contextlib.suppress(RuntimeError):
            if worker.isRunning():
                worker.wait()
    self._trash_workers.clear()
    self._flush_pending_trash()


def _flush_pending_trash(self) -> None:
    """Trash whatever is still queued inline — we are shutting down.

    The worker we just joined never delivered its queued ``finished_with``
    (no event loop is left to run the slot), so nothing will pump the
    queue. Without this, deletes the user already confirmed would be
    dropped on the floor.
    """
    batch, self._pending_trash = self._pending_trash, []
    if not batch:
        return
    from Imervue.system.trash_ops import trash_batch

    trash_batch([path for request in batch for path in request.paths])
