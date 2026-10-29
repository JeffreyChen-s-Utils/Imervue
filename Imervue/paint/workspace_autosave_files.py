"""Ownership and cleanup of the Paint workspace's autosave files.

Split out of :mod:`workspace_autosave`; :class:`AutosaveFilesMixin` is a base of
:class:`Imervue.paint.workspace_autosave.AutosaveMixin`. It tracks which snapshot
bundles each tab wrote or recovered and deletes only those, logging files that
cannot be removed.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("Imervue")


class AutosaveFilesMixin:
    """Per-canvas snapshot paths and their deletion on close or discard."""

    def discard_canvas_autosaves(self, canvas) -> int:
        """Release one closed tab's snapshots and tracking, leaving others alone."""
        jobs = getattr(self, "_autosave_jobs", None)
        record = getattr(self, "_autosave_records", {}).get(canvas)
        if jobs is not None and record is not None:
            jobs.cancel(record[1])
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
        for path in tuple(paths):   # the caller's collection may shrink as files go
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
        jobs = getattr(self, "_autosave_jobs", None)
        if jobs is not None:
            jobs.cancel_all()
        written = getattr(self, "_autosave_written", None) or set()
        return self._discard_autosave_paths(written)
