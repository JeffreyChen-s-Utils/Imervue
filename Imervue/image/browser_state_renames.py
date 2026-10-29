"""Same-file rename inference and per-path viewer cache migration."""
from __future__ import annotations

import os
from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path

from Imervue.image.browser_state_index import ImageMetadataIndex


def detect_renamed_paths(old_paths: Iterable[str], new_paths: Iterable[str],
                         index: ImageMetadataIndex | None = None) -> dict[str, str]:
    """Infer same-file renames so thumbnail/metadata cache can migrate."""
    old_paths, new_paths = list(old_paths), list(new_paths)
    old_set, new_set = set(old_paths), set(new_paths)
    old_only = [p for p in old_paths if p not in new_set]
    new_only = [p for p in new_paths if p not in old_set]
    if not old_only or not new_only:
        return {}
    old_sig: dict[tuple[int, int, str], list[str]] = {}
    for path in old_only:
        sig = _rename_signature(path, index)
        if sig is not None:
            old_sig.setdefault(sig, []).append(path)

    mapping: dict[str, str] = {}
    used_old: set[str] = set()
    for new_path in new_only:
        sig = _rename_signature(new_path, index)
        if sig is None:
            continue
        candidates = [p for p in old_sig.get(sig, []) if p not in used_old]
        if not candidates:
            continue
        stem = Path(new_path).stem.lower()
        old_path = max(
            candidates,
            key=lambda p, stem=stem: SequenceMatcher(None, Path(p).stem.lower(), stem).ratio(),
        )
        used_old.add(old_path)
        mapping[old_path] = new_path
    return mapping


def _rename_signature(
    path: str,
    index: ImageMetadataIndex | None = None,
) -> tuple[int, int, str] | None:
    if index is not None:
        meta = index.get_stat(path)
        if meta.size or meta.mtime_ns:
            return (meta.size, meta.mtime_ns, meta.suffix)
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns, Path(path).suffix.lower())


def migrate_view_path_state(view, mapping: dict[str, str]) -> None:
    """Move per-path viewer caches for inferred renames."""
    if not mapping:
        return
    attrs = (
        "tile_cache",
        "tile_errors",
        "_tile_load_times",
        "_filmstrip_thumb_cache",
        "tile_textures",
        "_tile_tex_sizes",
        "_view_memory",
    )
    for old, new in mapping.items():
        for attr in attrs:
            data = getattr(view, attr, None)
            if isinstance(data, dict) and old in data and new not in data:
                data[new] = data.pop(old)
        for attr in (
            "offline_paths", "_tile_error_toasted", "_filmstrip_pending", "selected_tiles",
        ):
            data = getattr(view, attr, None)
            if isinstance(data, set) and old in data:
                data.discard(old)
                data.add(new)

