"""Files a folder listing leaves out: hidden ones, and the dot-files macOS leaves on drives.

Explorer and the folder tree (``QFileSystemModel``'s default filter) leave out
a file Windows marks hidden; the thumbnail wall and the batch tools listed them
anyway, and a recursive batch over a drive's root walked into ``$RECYCLE.BIN``.
A name starting with a dot is hidden by convention everywhere else, and macOS
writes such names onto every FAT, exFAT or network drive it touches: a
``._photo.jpg`` AppleDouble resource fork beside each photo (an image
extension, never an image - a broken thumbnail beside every photo, a failure
in every batch), ``.Trashes`` holding the photos deleted on the Mac,
``.Spotlight-V100``. So a leading dot counts as hidden on Windows too.
"""
from __future__ import annotations

import os
import stat
import sys


def is_hidden(entry: os.DirEntry | str | os.PathLike[str]) -> bool:
    """True for a name starting with a dot, or a file Windows marks hidden.

    A ``DirEntry`` answers from the attributes its directory listing already
    read; a path costs one ``stat`` on Windows. A file that can't be read
    counts as not hidden.
    """
    name = entry.name if isinstance(entry, os.DirEntry) else os.path.basename(os.fspath(entry))
    if name.startswith("."):
        return True
    if sys.platform != "win32":
        return False
    try:
        info = (entry.stat(follow_symlinks=False) if isinstance(entry, os.DirEntry)
                else os.stat(entry, follow_symlinks=False))
    except OSError:
        return False
    return bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_HIDDEN)
