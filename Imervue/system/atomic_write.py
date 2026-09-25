"""Replace a file in one step, so a failed or interrupted write never leaves it half-written.

Writing straight to a path truncates it the moment it is opened: a full disk,
a crash or an exception mid-write then leaves the only copy broken. Every
save over an existing user file goes through :func:`replace_atomically`,
which writes a ``.tmp`` sibling and swaps it in with ``os.replace``.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


def replace_atomically(path: str | Path, write: Callable[[Path], None]) -> None:
    """Replace *path* with what *write* puts in a ``.tmp`` sibling, in one step.

    A crash or an error mid-write leaves the original whole: the sibling is
    removed and the error propagates. *write* gets the sibling's path, whose
    extension is ``.tmp``, so a Pillow save must name its ``format=``.
    """
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def write_text_atomically(path: str | Path, text: str) -> None:
    """Replace *path* with *text* (UTF-8) in one step; see :func:`replace_atomically`."""
    replace_atomically(path, lambda tmp: tmp.write_text(text, encoding="utf-8"))
