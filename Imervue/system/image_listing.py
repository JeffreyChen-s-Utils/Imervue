"""List a folder's images the way every batch tool does: by extension, in natural name order.

Batch Convert, EXIF Strip, the Image Organizer, Image Sanitize, AI Upscale and
Duplicate Detection each pick a source folder and work through its images;
:func:`list_images` is the one listing they share.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from pathlib import Path

from Imervue.system.natural_sort import natural_key

logger = logging.getLogger("Imervue.image_listing")


def list_images(folder: str, extensions: Iterable[str], *, recursive: bool = False,
                should_stop: Callable[[], bool] | None = None) -> list[str]:
    """Paths of the files in *folder* whose lower-cased extension is in *extensions*.

    In natural order by file name (``img2`` before ``img10``). *recursive*
    walks the sub-folders too, and *should_stop* is asked before each folder:
    True ends the walk with what was found so far. A folder that can't be
    read lists what was read before the error; nothing raises.
    """
    exts = frozenset(extensions)
    found = _walk(folder, exts, should_stop) if recursive else _scan(folder, exts)
    found.sort(key=lambda path: natural_key(os.path.basename(path)))
    return found


def _scan(folder: str, exts: frozenset[str]) -> list[str]:
    found: list[str] = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.is_file() and Path(entry.name).suffix.lower() in exts:
                    found.append(entry.path)
    except OSError as exc:
        logger.debug("Listing %s stopped: %s", folder, exc)
    return found


def _walk(folder: str, exts: frozenset[str], should_stop: Callable[[], bool] | None) -> list[str]:
    found: list[str] = []
    for root, _dirs, files in os.walk(folder):
        if should_stop is not None and should_stop():
            break
        found.extend(os.path.join(root, name) for name in files
                     if Path(name).suffix.lower() in exts)
    return found
