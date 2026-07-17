"""_FileTreeView.shutdown must wait in-flight OS-trash workers.

FileDeleteWorker is parented to the tree view, so a secondary window closing
(which deleteLater's the view) would destroy a still-running worker thread
('QThread: Destroyed while thread is still running'). shutdown() joins them
first. Driven on the method with fakes -- no Qt view constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.file_tree_view import _FileTreeView


class _FakeWorker:
    def __init__(self, running: bool):
        self._running = running
        self.waited = False

    def isRunning(self) -> bool:   # noqa: N802 - mirrors Qt's camelCase API
        return self._running

    def wait(self):
        self.waited = True


def test_shutdown_waits_running_workers_and_clears():
    running = _FakeWorker(running=True)
    idle = _FakeWorker(running=False)
    view = SimpleNamespace(_trash_workers={running, idle})

    _FileTreeView.shutdown(view)

    assert running.waited is True
    assert idle.waited is False          # not running -> not waited
    assert view._trash_workers == set()  # registry cleared


def test_shutdown_with_no_workers_is_noop():
    view = SimpleNamespace(_trash_workers=set())
    _FileTreeView.shutdown(view)         # must not raise
    assert view._trash_workers == set()


def test_shutdown_tolerates_wait_raising_runtime_error():
    class _BrokenWorker:
        def isRunning(self):   # noqa: N802 - mirrors Qt's camelCase API
            return True

        def wait(self):
            raise RuntimeError("C++ object already deleted")

    view = SimpleNamespace(_trash_workers={_BrokenWorker()})
    _FileTreeView.shutdown(view)         # RuntimeError suppressed, must not raise
    assert view._trash_workers == set()
