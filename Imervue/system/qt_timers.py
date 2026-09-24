"""Deferred calls that die with the object they belong to.

``QTimer.singleShot(ms, fn)`` keeps *fn* alive on its own: if the object *fn*
belongs to is destroyed first, the call still runs and touches a deleted C++
object (``RuntimeError: Internal C++ object already deleted``). That holds for
a lambda and equally for a bound method: measured on PySide6 6.11, both a
Python method and a C++ slot such as ``widget.update`` still ran after the
widget was deleted. Only the ``singleShot(ms, context, callable)`` overload
lets Qt drop the call when ``context`` is destroyed, and ``call_later`` is that.
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
