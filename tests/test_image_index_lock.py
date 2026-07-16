"""write_batch must hold the lock for its whole body, not just BEGIN/COMMIT.

Releasing it during the transaction let a concurrent UI-thread write (sharing the
connection) execute inside the scanner's open transaction and be rolled back with
it. The reentrant lock is now held across the entire body.
"""
from __future__ import annotations

import threading

from Imervue.library import image_index


class _StubConn:
    def execute(self, _sql):   # noqa: D401 - stub
        return None


def test_lock_is_held_across_the_whole_body(monkeypatch):
    monkeypatch.setattr(image_index, "conn", lambda: _StubConn())
    other_thread_got_lock: list = []

    def _try_acquire():
        got = image_index._lock.acquire(blocking=False)
        other_thread_got_lock.append(got)
        if got:
            image_index._lock.release()

    with image_index.write_batch():
        # Inside the transaction body, another thread must NOT be able to take
        # the lock (and slip a write into this transaction).
        thread = threading.Thread(target=_try_acquire)
        thread.start()
        thread.join()

    assert other_thread_got_lock == [False]
