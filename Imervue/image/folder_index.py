"""Per-folder image list cache for the sorts that read every file's header.

A cached order is reused while the folder's modification time is unchanged and
every listed file still has the modification time and size it had when saved.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# Bumped when the order a cache holds changes meaning: 2 = names in natural
# order (img2 before img10); 3 = each image saved with its mtime and size.
# An older cache is ignored and rewritten.
_FORMAT = 3


def _cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "cache" / "folder_index"
    return Path.home() / ".cache" / "imervue" / "folder_index"


def _cache_path(folder: str) -> Path:
    # Justification: folder comes from the local file tree.
    key = hashlib.sha256(str(Path(folder).resolve()).encode()).hexdigest()  # NOSONAR
    return _cache_dir() / f"{key}.json"


def _stamp(path: str) -> list[int] | None:
    """``[mtime_ns, size]`` of *path*, or None when it is gone."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return [st.st_mtime_ns, st.st_size]


def load(folder: str, *, sort_by: str, ascending: bool) -> list[str] | None:
    """The cached order, or None when it may no longer be right."""
    try:
        st = Path(folder).stat()  # NOSONAR folder comes from the local file tree, not remote input
        data = json.loads(_cache_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("format") != _FORMAT or data.get("folder_mtime_ns") != st.st_mtime_ns:
        return None
    if data.get("sort_by") != sort_by or data.get("ascending") != ascending:
        return None
    paths, stamps = data.get("images"), data.get("stamps")
    if not isinstance(paths, list) or not isinstance(stamps, list) or len(stamps) != len(paths):
        return None
    kept = []
    for path, stamp in zip(paths, stamps, strict=True):
        now = _stamp(path) if isinstance(path, str) else None
        if now is None:
            continue   # deleted since: the rest keep their order
        if now != stamp:
            # Rewritten in place (an editor saving over it, a new EXIF date): the
            # folder's time did not move, but its size or date may sort it elsewhere.
            return None
        kept.append(path)
    return kept


def save(folder: str, images: list[str], *, sort_by: str, ascending: bool) -> None:
    """Remember *images* as *folder*'s order for this sort; a failed write is skipped."""
    try:
        st = Path(folder).stat()  # NOSONAR folder comes from the local file tree, not remote input
        out = _cache_path(folder)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "format": _FORMAT,
                    "folder_mtime_ns": st.st_mtime_ns,
                    "sort_by": sort_by,
                    "ascending": ascending,
                    "images": images,
                    "stamps": [_stamp(path) for path in images],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        return

