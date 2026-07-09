"""Per-folder image list cache."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def _cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "cache" / "folder_index"
    return Path.home() / ".cache" / "imervue" / "folder_index"


def _cache_path(folder: str) -> Path:
    key = hashlib.md5(str(Path(folder).resolve()).encode(), usedforsecurity=False).hexdigest()
    return _cache_dir() / f"{key}.json"


def load(folder: str, *, sort_by: str, ascending: bool) -> list[str] | None:
    try:
        st = Path(folder).stat()
        data = json.loads(_cache_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if data.get("folder_mtime_ns") != st.st_mtime_ns:
        return None
    if data.get("sort_by") != sort_by or data.get("ascending") != ascending:
        return None
    paths = data.get("images")
    if not isinstance(paths, list):
        return None
    return [p for p in paths if isinstance(p, str) and Path(p).exists()]


def save(folder: str, images: list[str], *, sort_by: str, ascending: bool) -> None:
    try:
        st = Path(folder).stat()
        out = _cache_path(folder)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "folder_mtime_ns": st.st_mtime_ns,
                    "sort_by": sort_by,
                    "ascending": ascending,
                    "images": images,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        return

