"""Synchronous stand-in for ``trash_ops.FileDeleteWorker`` shared by tests.

``start()`` runs the whole "thread" inline: it fires one progress update and
then ``finished_with`` with every path reported as trashed, so tests can
assert the post-delete state immediately without spinning an event loop.
"""
from __future__ import annotations

from types import SimpleNamespace


class InstantDeleteWorker:
    """Duck-typed FileDeleteWorker that completes synchronously in start()."""

    created: list = []

    def __init__(self, paths, parent=None) -> None:
        self.paths = list(paths)
        self._progress_cbs: list = []
        self._finished_cbs: list = []
        self.progress = SimpleNamespace(connect=self._progress_cbs.append)
        self.finished_with = SimpleNamespace(connect=self._finished_cbs.append)
        InstantDeleteWorker.created.append(self)

    def start(self) -> None:
        total = len(self.paths)
        for callback in self._progress_cbs:
            callback(total, total)
        for callback in self._finished_cbs:
            callback(list(self.paths), [])

    def deleteLater(self) -> None:  # noqa: N802 - mirrors QObject
        """No-op; the fake owns no Qt resources."""


class FailingDeleteWorker(InstantDeleteWorker):
    """Variant that reports every path as failed."""

    def start(self) -> None:
        for callback in self._finished_cbs:
            callback([], list(self.paths))
