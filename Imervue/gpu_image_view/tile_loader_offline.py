"""Thumbnail-wall file sweep: missing, recovered and rewritten files.

A background worker stats every folder path; its result flips tiles to and
from the 'Missing' state, reloads recovered and rewritten thumbnails, and has
the list view read the changed rows again. Split from :mod:`tile_loader`,
which owns the sweep timer and re-exports the public names.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, Signal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def file_signature(path: str) -> tuple[int, int, str] | None:
    """``(size, mtime_ns, suffix)`` of *path*, or None when it can't be stat'ed."""
    try:
        # *path* is the picture the viewer is showing, from the user's own folder.
        st = os.stat(path)  # NOSONAR
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns, Path(path).suffix.lower())


class _OfflineScanSignals(QObject):
    finished = Signal(object, int, object)  # missing set, load generation, rewritten set


class OfflineScanWorker(QRunnable):
    """Stat every folder path off the GUI thread; report the missing and the rewritten ones."""

    def __init__(self, paths: list[str], generation: int,
                 known: dict[str, tuple[int, int, str]] | None = None) -> None:
        super().__init__()
        self._paths = paths
        self._generation = generation
        self._known = known or {}
        self.signals = _OfflineScanSignals()

    def run(self) -> None:
        missing, rewritten = scan_folder_paths(self._paths, self._known)
        self.signals.finished.emit(missing, self._generation, rewritten)


def scan_folder_paths(paths, known) -> tuple[set[str], set[str]]:
    """Pure sweep body: ``(missing, rewritten)`` among *paths*, one stat each.

    Missing: no longer on disk. Rewritten: still there, but its size or
    modification time moved away from the signature *known* recorded when its
    thumbnail was decoded - another program saved over it. A path *known*
    has no signature for is never rewritten.
    """
    missing: set[str] = set()
    rewritten: set[str] = set()
    for path in paths:
        signature = file_signature(path)
        if signature is None:
            missing.add(path)
        elif path in known and known[path] != signature:
            rewritten.add(path)
    return missing, rewritten


def on_offline_scan_finished(view: GPUImageView, missing, generation: int, rewritten=()) -> None:
    """Apply one sweep result: flip offline states, reload recovered and rewritten tiles."""
    view._offline_scan_inflight = False
    if generation != view._load_generation:
        return
    current = set(view.model.images)
    missing = set(missing) & current
    rewritten = (set(rewritten) & current) - missing
    for path in rewritten:
        refresh_rewritten_tile(view, path, generation)
    offline = getattr(view, "offline_paths", set())
    recovered = (offline & current) - missing
    newly_missing = missing - offline
    refetch_list_rows(view, rewritten | recovered | newly_missing)
    if not recovered and not newly_missing:
        return
    offline.difference_update(recovered)
    offline.update(newly_missing)
    _report_offline_changes(view, newly_missing, recovered, generation)
    view.update()


def _report_offline_changes(view: GPUImageView, newly_missing: set[str],
                            recovered: set[str], generation: int) -> None:
    # Worker spawning lives in tile_loader, which imports this module.
    from Imervue.gpu_image_view.tile_loader import _retry_thumbnail

    record_issue = getattr(view.main_window, "record_image_issue", None)
    clear_issue = getattr(view.main_window, "clear_image_issue", None)
    if record_issue is not None:
        for path in newly_missing:
            record_issue(path, "File not found")
    for path in recovered:
        if clear_issue is not None:
            clear_issue(path)
        # The tile was drawn as "Missing" while offline — reload it now that
        # the file is back (drive re-mounted, file restored).
        if path not in view.tile_cache:
            _retry_thumbnail(view, path, generation)


def refresh_rewritten_tile(view: GPUImageView, path: str, generation: int) -> None:
    """Decode *path*'s thumbnail again: another program rewrote the file.

    The old thumbnail stays on screen until the new one lands (which also
    replaces its texture). The filmstrip copy and a prefetched full decode go
    now, so paging to the picture shows the new pixels.
    """
    getattr(view, "_tile_file_signatures", {}).pop(path, None)   # the new decode records it again
    getattr(view, "_filmstrip_thumb_cache", {}).pop(path, None)
    prefetch = getattr(view, "_prefetch", None)
    if prefetch is not None:
        prefetch.discard(path)
    # Worker spawning lives in tile_loader, which imports this module.
    from Imervue.gpu_image_view.tile_loader import _retry_thumbnail
    _retry_thumbnail(view, path, generation, replay=True)


def refetch_list_rows(view: GPUImageView, paths) -> None:
    """Have the list view read *paths* again: rewritten, gone, or back on disk.

    One call per batch: the list finds its rows in a single pass.
    """
    refetch = getattr(view.main_window, "refetch_list_rows", None)
    if refetch is not None and paths:
        refetch(set(paths))
