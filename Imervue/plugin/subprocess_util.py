"""Shared subprocess helpers for plugin workers that shell out to a child
Python (frozen-env rembg, object splitting, background removal, ...).

Centralises the terminate-then-kill dance so a cancelled worker's child
process is reaped instead of orphaned, and so the worker's QThread — which
blocks reading the child's stdout — unblocks (the pipe closes) and its
``wait()`` returns instead of hanging. Kept Qt-free so it is unit-testable
without a QApplication.
"""

from __future__ import annotations

import contextlib
import subprocess

_TERMINATE_GRACE_SECONDS = 2


def terminate_process(proc: subprocess.Popen | None) -> None:
    """Stop *proc* if it is still running: terminate, then kill on timeout.

    A no-op when *proc* is ``None`` or has already exited (``poll()`` is not
    ``None``). ``terminate()`` is given a short grace period to let the child
    flush and exit cleanly; if it overruns, ``kill()`` forces it down. Any
    error from the child (already-reaped race, permission) is suppressed — the
    goal is best-effort reaping, never to raise out of a cancel path.
    """
    if proc is None or proc.poll() is not None:
        return
    with contextlib.suppress(Exception):
        proc.terminate()
        try:
            proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
