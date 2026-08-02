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
    # Justification: folder comes from the local file tree.
    key = hashlib.sha256(str(Path(folder).resolve()).encode()).hexdigest()  # NOSONAR
    return _cache_dir() / f"{key}.json"


def load(folder: str, *, sort_by: str, ascending: bool) -> list[str] | None:
    try:
        st = Path(folder).stat()  # NOSONAR folder comes from the local file tree, not remote input
        data = json.loads(_cache_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
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
        st = Path(folder).stat()  # NOSONAR folder comes from the local file tree, not remote input
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

