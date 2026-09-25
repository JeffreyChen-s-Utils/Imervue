"""First free file names in a folder: ``photo_clahe.png``, then ``photo_clahe_1.png``.

A tool that writes a new file beside the user's own must never pick a name that
is already taken: the file there may be an earlier result retouched since, or a
different photo that happens to share the name.
"""
from __future__ import annotations

import os
from pathlib import Path


def free_names(directory: str | os.PathLike, stems: list[str], ext: str) -> list[Path]:
    """Paths ``<directory>/<stem><tail><ext>`` for each of *stems*, none of which exists yet.

    The tail is empty, then ``_1``, ``_2`` and on. One number serves the whole
    group, so files written together (frequency separation's low and high
    layers, a split document's pages) stay recognisable as a set. Names are
    compared the way the file system does; a folder that cannot be listed
    counts as empty.
    """
    folder = Path(directory)
    try:
        taken = {os.path.normcase(name) for name in os.listdir(folder)}
    except OSError:
        taken = set()
    counter = 0
    while True:
        tail = f"_{counter}" if counter else ""
        names = [f"{stem}{tail}{ext}" for stem in stems]
        if not any(os.path.normcase(name) in taken for name in names):
            return [folder / name for name in names]
        counter += 1
