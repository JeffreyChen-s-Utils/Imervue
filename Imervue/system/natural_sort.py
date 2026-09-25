"""Order file names the way Explorer does: ``img2`` before ``img10``.

A plain string sort compares digit by digit, so ``page10`` lands between
``page1`` and ``page2`` - wrong for scans, comic pages and camera numbering.
The file tree already compares names with a numeric-mode ``QCollator``; the
viewer's own order (grid, next / previous, batch lists) uses this Qt-free key
so both show the same sequence.
"""
from __future__ import annotations

import re

_DIGIT_RUN = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple:
    """Sort key for *name*: case-insensitive, digit runs compared by value.

    ``img2`` < ``img10`` < ``IMG11``. Runs of any Unicode decimal digits count
    (full-width ``１２`` too). Names equal by that rule (``a01`` and ``a1``,
    ``A`` and ``a``) fall back to the case-folded, then the exact name, so the
    order never depends on the order they came in.
    """
    folded = name.casefold()
    parts = _DIGIT_RUN.split(folded)
    # split() alternates text, digits, text ... starting with text, so two keys
    # always compare str with str and int with int at each position.
    runs = tuple(int(part) if index % 2 else part for index, part in enumerate(parts))
    return runs, folded, name
