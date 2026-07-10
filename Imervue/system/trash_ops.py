"""Background trash operations for large batch deletes.

Sending one file to the OS recycle bin is a full shell round-trip — tens of
milliseconds each on Windows — so a per-file loop over a large selection
freezes the GUI thread for its whole duration. :func:`trash_batch` groups
paths into chunks (one shell operation per chunk, with a per-file fallback
that isolates failures) and :class:`FileDeleteWorker` runs it on a
background thread, reporting progress and the final outcome via signals.

``trash_batch`` is pure apart from the injected trash calls and is
unit-tested without Qt.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("Imervue.trash_ops")

# One shell operation per chunk keeps the syscall count low while still
# yielding progress updates often enough for a visible progress bar.
TRASH_CHUNK_SIZE = 64


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


def trash_batch(
    paths: Sequence[str],
    on_progress: Callable[[int, int], None] | None = None,
    chunk_size: int = TRASH_CHUNK_SIZE,
) -> tuple[list[str], list[str]]:
    """Move *paths* to the OS trash in chunks; returns ``(trashed, failed)``.

    Paths that no longer exist are skipped silently (already gone counts as
    done). *on_progress* is called after each chunk with ``(done, total)``.
    """
    trashed: list[str] = []
    failed: list[str] = []
    total = len(paths)
    for start in range(0, total, chunk_size):
        group = [p for p in paths[start:start + chunk_size] if Path(p).exists()]
        if group:
            succeeded, bad = _trash_chunk(group)
            trashed.extend(succeeded)
            failed.extend(bad)
        if on_progress is not None:
            on_progress(min(start + chunk_size, total), total)
    return trashed, failed


class FileDeleteWorker(QThread):
    """Run :func:`trash_batch` off the GUI thread.

    ``progress`` fires with ``(done, total)`` per chunk; ``finished_with``
    fires once with ``(trashed_paths, failed_paths)``.
    """

    progress = Signal(int, int)
    finished_with = Signal(list, list)

    def __init__(self, paths: Sequence[str], parent=None) -> None:
        super().__init__(parent)
        self._paths = list(paths)

    def run(self) -> None:
        trashed, failed = trash_batch(self._paths, self.progress.emit)
        for path in failed:
            logger.warning("Failed to move to trash: %s", path)
        self.finished_with.emit(trashed, failed)
