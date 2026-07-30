"""_FileTreeView.shutdown must drain the OS-trash work before teardown.

FileDeleteWorker is parented to the tree view, so a secondary window closing
(which deleteLater's the view) would destroy a still-running worker thread
('QThread: Destroyed while thread is still running'). shutdown() joins them
first, then flushes anything still queued behind them — the joined worker's
``finished_with`` is never delivered at that point (no event loop is left to
run the slot), so nothing else would pump the queue. Driven on the method
with fakes -- no Qt view constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.file_tree_view import _FileTreeView, _TrashRequest


class _FakeWorker:
    def __init__(self, running: bool):
        self._running = running
        self.waited = False

    def isRunning(self) -> bool:   # noqa: N802 - mirrors Qt's camelCase API
        return self._running

    def wait(self):
        self.waited = True


def _fake_view(workers=(), pending=()) -> SimpleNamespace:
    """Namespace exposing exactly the attributes ``shutdown`` touches."""
    view = SimpleNamespace(_trash_workers=set(workers), _pending_trash=list(pending))
    view._flush_pending_trash = lambda: _FileTreeView._flush_pending_trash(view)
    return view


def test_shutdown_waits_running_workers_and_clears():
    running = _FakeWorker(running=True)
    idle = _FakeWorker(running=False)
    view = _fake_view({running, idle})

    _FileTreeView.shutdown(view)

    assert running.waited is True
    assert idle.waited is False          # not running -> not waited
    assert view._trash_workers == set()  # registry cleared


def test_shutdown_with_no_workers_is_noop():
    view = _fake_view()
    _FileTreeView.shutdown(view)         # must not raise
    assert view._trash_workers == set()


def test_shutdown_tolerates_wait_raising_runtime_error():
    class _BrokenWorker:
        def isRunning(self):   # noqa: N802 - mirrors Qt's camelCase API
            return True

        def wait(self):
            raise RuntimeError("C++ object already deleted")

    view = _fake_view({_BrokenWorker()})
    _FileTreeView.shutdown(view)         # RuntimeError suppressed, must not raise
    assert view._trash_workers == set()


# ---------------------------------------------------------------------------
# Queue flush
# ---------------------------------------------------------------------------


def _capture_trash(monkeypatch) -> list[list[str]]:
    """Record the groups handed to the batch helper instead of trashing."""
    from Imervue.system import trash_ops
    calls: list[list[str]] = []
    monkeypatch.setattr(trash_ops, "trash_batch",
                        lambda paths: calls.append(list(paths)) or ([], []))
    return calls


def test_shutdown_flushes_queued_requests_inline(monkeypatch):
    calls = _capture_trash(monkeypatch)
    view = _fake_view(
        {_FakeWorker(running=True)},
        [_TrashRequest(("/a.png",), lambda _done: None),
         _TrashRequest(("/b.png", "/c.png"), lambda _done: None)],
    )

    _FileTreeView.shutdown(view)

    # One grouped call for everything left over, and the queue is emptied.
    assert calls == [["/a.png", "/b.png", "/c.png"]]
    assert view._pending_trash == []


def test_shutdown_with_an_empty_queue_calls_nothing(monkeypatch):
    calls = _capture_trash(monkeypatch)
    view = _fake_view()
    _FileTreeView.shutdown(view)
    assert calls == []
