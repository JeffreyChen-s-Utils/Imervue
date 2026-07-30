"""Background trash / permanent-delete operations for large batch deletes.

Sending one file to the OS recycle bin is a full shell round-trip — measured
at ~0.27 s per call on Windows, against ~0.016 s per file when the same files
are handed over in one grouped call — so a per-file loop over a large
selection freezes the GUI thread for minutes. :func:`trash_batch` and
:func:`purge_batch` group paths into chunks (one shell operation per chunk,
with a per-file fallback that isolates failures) and the workers run them on
a background thread, reporting progress and the final outcome via signals.

The batch functions are pure apart from the injected trash / unlink calls and
are unit-tested without Qt.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("Imervue.trash_ops")

# One shell operation per chunk keeps the syscall count low while still
# yielding progress updates often enough for a visible progress bar.
TRASH_CHUNK_SIZE = 64

ProgressCallback = Callable[[int, int], None]
# A chunk handler applies one operation to a group and returns
# ``(succeeded, failed)`` so a partial failure never loses the good paths.
ChunkHandler = Callable[[Sequence[str]], tuple[list[str], list[str]]]


def _trash_many(paths: Sequence[str]) -> None:
    """One shell operation for the whole group (send2trash accepts lists)."""
    from send2trash import send2trash
    send2trash(list(paths))


def _trash_chunk(paths: Sequence[str]) -> tuple[list[str], list[str]]:
    """Trash one chunk; on a batch failure retry per file to isolate it."""
    try:
        _trash_many(paths)
        return list(paths), []
    except Exception:  # noqa: BLE001 — send2trash raises mixed OSError/TrashPermissionError/ImportError; isolate below
        from Imervue.gpu_image_view.actions.keyboard_actions import _send_to_trash
        succeeded: list[str] = []
        failed: list[str] = []
        for path in paths:
            (succeeded if _send_to_trash(path) else failed).append(path)
        return succeeded, failed


def _unlink_chunk(paths: Sequence[str]) -> tuple[list[str], list[str]]:
    """Permanently remove one chunk; each failure is isolated to its path."""
    succeeded: list[str] = []
    failed: list[str] = []
    for path in paths:
        try:
            Path(path).unlink()
        except OSError:
            failed.append(path)
        else:
            succeeded.append(path)
    return succeeded, failed


class _ProgressReporter:
    """Accumulating ``(done, total)`` reporter shared across chunk groups.

    A purge spans two groups (unlinked files, then trashed ones) but drives a
    single progress bar, so the running count has to survive across them.
    """

    def __init__(self, total: int, report: ProgressCallback | None) -> None:
        self._done = 0
        self._total = total
        self._report = report

    def advance(self, count: int) -> None:
        self._done = min(self._done + count, self._total)
        if self._report is not None:
            self._report(self._done, self._total)


def _apply_in_chunks(
    paths: Sequence[str],
    handler: ChunkHandler,
    chunk_size: int,
    reporter: _ProgressReporter,
) -> tuple[list[str], list[str]]:
    """Hand *paths* to *handler* one chunk at a time; ``(succeeded, failed)``.

    Paths that no longer exist are skipped silently (already gone counts as
    done); the reporter advances once per chunk, not per file.
    """
    succeeded: list[str] = []
    failed: list[str] = []
    total = len(paths)
    for start in range(0, total, chunk_size):
        group = [p for p in paths[start:start + chunk_size] if Path(p).exists()]
        if group:
            good, bad = handler(group)
            succeeded.extend(good)
            failed.extend(bad)
        reporter.advance(min(chunk_size, total - start))
    return succeeded, failed


def trash_batch(
    paths: Sequence[str],
    on_progress: ProgressCallback | None = None,
    chunk_size: int = TRASH_CHUNK_SIZE,
) -> tuple[list[str], list[str]]:
    """Move *paths* to the OS trash in chunks; returns ``(trashed, failed)``.

    *on_progress* is called after each chunk with ``(done, total)``.
    """
    paths = list(paths)
    return _apply_in_chunks(
        paths, _trash_chunk, chunk_size,
        _ProgressReporter(len(paths), on_progress),
    )


def purge_batch(
    unlink_paths: Sequence[str],
    trash_paths: Sequence[str] = (),
    on_progress: ProgressCallback | None = None,
    chunk_size: int = TRASH_CHUNK_SIZE,
) -> tuple[list[str], list[str]]:
    """Delete *unlink_paths* outright and send *trash_paths* to the OS trash.

    Callers that commit a soft delete hold both kinds at once: viewer-list
    images were already removed from the list and are unlinked, while
    folders / file-tree entries were only hidden, so they go to the OS bin
    and stay recoverable from there. Both groups share one progress count so
    the caller shows a single bar. Returns ``(removed, failed)`` over both.
    """
    unlink_paths = list(unlink_paths)
    trash_paths = list(trash_paths)
    reporter = _ProgressReporter(len(unlink_paths) + len(trash_paths), on_progress)
    removed, failed = _apply_in_chunks(
        unlink_paths, _unlink_chunk, chunk_size, reporter)
    trashed, trash_failed = _apply_in_chunks(
        trash_paths, _trash_chunk, chunk_size, reporter)
    return removed + trashed, failed + trash_failed


class _BatchFileWorker(QThread):
    """Runs one bound chunked file operation off the GUI thread.

    *operation* takes a progress callback and returns
    ``(succeeded, failed)`` — bound by the subclass so this class stays
    agnostic about which operation it is driving.

    ``progress`` fires with ``(done, total)`` per chunk; ``finished_with``
    fires once with ``(succeeded_paths, failed_paths)``.
    """

    progress = Signal(int, int)
    finished_with = Signal(list, list)

    def __init__(
        self,
        operation: Callable[[ProgressCallback], tuple[list[str], list[str]]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation

    def run(self) -> None:
        succeeded, failed = self._operation(self.progress.emit)
        for path in failed:
            logger.warning("Batch delete failed on: %s", path)
        self.finished_with.emit(succeeded, failed)


class FileDeleteWorker(_BatchFileWorker):
    """Move *paths* to the OS trash off the GUI thread."""

    def __init__(self, paths: Iterable[str], parent=None) -> None:
        snapshot = list(paths)
        super().__init__(lambda report: trash_batch(snapshot, report), parent)


class FilePurgeWorker(_BatchFileWorker):
    """Unlink *unlink_paths* and trash *trash_paths* off the GUI thread."""

    def __init__(
        self,
        unlink_paths: Iterable[str],
        trash_paths: Iterable[str] = (),
        parent=None,
    ) -> None:
        to_unlink = list(unlink_paths)
        to_trash = list(trash_paths)
        super().__init__(
            lambda report: purge_batch(to_unlink, to_trash, report), parent)
