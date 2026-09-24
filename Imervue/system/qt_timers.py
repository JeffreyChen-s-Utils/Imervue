"""Deferred calls that die with the object they belong to.

``QTimer.singleShot(ms, lambda: self.x())`` keeps the lambda alive on its own:
if ``self`` is destroyed first, the lambda still runs and touches a deleted C++
object (``RuntimeError: Internal C++ object already deleted``). The
``singleShot(ms, context, callable)`` overload lets Qt drop the call when
``context`` is destroyed; a bound method of a ``QObject`` gets the same
treatment automatically, a lambda or closure does not.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer


def call_later(ms: int, owner: object, fn: Callable[[], object]) -> None:
    """Run *fn* after *ms* milliseconds, unless the ``QObject`` *owner* is destroyed first.

    An *owner* that is not a ``QObject`` (a test double) falls back to a plain
    timer, which is what the call site had before.
    """
    if isinstance(owner, QObject):
        QTimer.singleShot(int(ms), owner, fn)
    else:
        QTimer.singleShot(int(ms), fn)
