"""Shared image-browser state helpers.

Small, UI-agnostic utilities for folder filtering, missing-file repair,
metadata indexing, and incremental cache migration.  Keeping this logic out
of the widgets makes folder refreshes testable and keeps large-directory
paths from drifting between grid/list/deep-zoom modes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from collections.abc import Iterable
import contextlib
import hashlib
import os
from pathlib import Path
from difflib import SequenceMatcher


@dataclass(frozen=True)
class ImageMeta:
    path: str
    name: str
    suffix: str
    size: int
    mtime_ns: int
    mtime_date: date | None
    width: int | None = None
    height: int | None = None


class ImageMetadataIndex:
    """Cheap stat-backed metadata cache for one browsing session."""

    def __init__(self) -> None:
        self._items: dict[str, ImageMeta] = {}
        self._hashes: dict[str, str] = {}

    def get(self, path: str) -> ImageMeta:
        meta = self._items.get(path)
        if meta is not None:
            return meta
        meta, cacheable = self._read(path)
        # Don't cache a transient stat failure (file mid-move, AV-locked, network
        # blip) — the zero-metadata sentinel would otherwise stick for the whole
        # session (dropping the image from date/size filters even after it
        # unlocks). Re-read next time instead.
        if cacheable:
            self._items[path] = meta
        return meta

    def prime(self, paths: Iterable[str], *, limit: int | None = None) -> None:
        for i, path in enumerate(paths):
            if limit is not None and i >= limit:
                break
            self.get(path)

    def drop_missing(self) -> None:
        for path in [p for p in self._items if not Path(p).exists()]:
            self._items.pop(path, None)

    def move(self, old_path: str, new_path: str) -> None:
        meta = self._items.pop(old_path, None)
        if meta is not None:
            self._items[new_path] = self._read(new_path)[0]
        digest = self._hashes.pop(old_path, None)
        if digest is not None:
            self._hashes[new_path] = digest

    def sample_hash(self, path: str) -> str:
        digest = self._hashes.get(path)
        if digest is not None:
            return digest
        digest = _sample_hash(path)
        if digest:
            self._hashes[path] = digest
        return digest

    @staticmethod
    def _read(path: str) -> tuple[ImageMeta, bool]:
        """Return ``(metadata, cacheable)``. ``cacheable`` is False when the
        ``stat`` failed transiently, so the caller shouldn't memoise the sentinel."""
        p = Path(path)
        cacheable = True
        try:
            st = p.stat()
            size = st.st_size
            mtime_ns = st.st_mtime_ns
            mtime_date = date.fromtimestamp(st.st_mtime)
        except OSError:
            size = 0
            mtime_ns = 0
            mtime_date = None
            cacheable = False
        width = height = None
        if size:
            with contextlib.suppress(Exception):
                from PIL import Image
                with Image.open(path) as img:
                    width, height = img.size
        return ImageMeta(
            path=path,
            name=p.name.lower(),
            suffix=p.suffix.lower(),
            size=size,
            mtime_ns=mtime_ns,
            mtime_date=mtime_date,
            width=width,
            height=height,
        ), cacheable


@dataclass(frozen=True)
class ImageFilterSpec:
    filename: str = ""
    tag: str = ""
    rating: str = ""
    date_from: date | None = None
    date_to: date | None = None
    raw_query: str = ""

    def is_empty(self) -> bool:
        return not any((
            self.filename.strip(),
            self.tag.strip(),
            self.rating.strip(),
            self.date_from,
            self.date_to,
            self.raw_query.strip(),
        ))


def match_filter(path: str, spec: ImageFilterSpec,
                 index: ImageMetadataIndex | None = None) -> bool:
    meta = index.get(path) if index is not None else ImageMetadataIndex._read(path)[0]
    filename = spec.filename.strip().lower()
    if filename and filename not in meta.name:
        return False
    if spec.tag.strip() and not _tag_matches(path, spec.tag):
        return False
    if spec.rating.strip() and not _rating_matches(path, spec.rating.strip()):
        return False
    if not _date_in_range(meta.mtime_date, spec.date_from, spec.date_to):
        return False
    return _match_raw_query(path, spec.raw_query, meta)


def _tag_matches(path: str, tag: str) -> bool:
    from Imervue.user_settings.tags import get_tags_for_image
    wanted = tag.strip().lower()
    return any(wanted in item.lower() for item in get_tags_for_image(path))


def _date_in_range(actual: date | None, date_from: date | None, date_to: date | None) -> bool:
    if not (date_from or date_to):
        return True
    if actual is None:
        return False
    if date_from and actual < date_from:
        return False
    return not (date_to and actual > date_to)


def filter_paths(paths: Iterable[str], spec: ImageFilterSpec,
                 index: ImageMetadataIndex | None = None) -> list[str]:
    if spec.is_empty():
        return list(paths)
    return [path for path in paths if match_filter(path, spec, index)]


def refilter_keeping_current(base: list[str], filtered: list[str],
                             current: str | None) -> list[str]:
    """Return *filtered*, but force *current* back in at its folder position.

    Opening a specific file (a Modify save, an image-tab switch) rebuilds the
    list from the full folder and drops the active browse filter. Re-applying
    the filter restores it, but the explicitly-opened image must stay visible
    even when it doesn't match — you asked to see that file — rather than the
    filter navigating away from it. Insert it back at its position in *base* so
    the strip/list keeps folder order. A no-op when *current* is falsy, already
    kept, or not part of *base*.
    """
    if not current or current in filtered or current not in base:
        return filtered
    pos_of = {path: i for i, path in enumerate(base)}
    current_pos = pos_of[current]
    insert_at = sum(1 for path in filtered if pos_of.get(path, -1) < current_pos)
    result = list(filtered)
    result.insert(insert_at, current)
    return result


def _match_raw_query(path: str, query: str, meta: ImageMeta) -> bool:
    tokens = [part for part in (query or "").split() if part]
    return all(_token_matches(path, token, meta) for token in tokens)


def _token_matches(path: str, token: str, meta: ImageMeta) -> bool:
    if token.startswith("tag:"):
        return _tag_matches(path, token[4:])
    if token.startswith("rating:"):
        return _rating_matches(path, token[7:])
    if token.startswith("date:"):
        wanted = token[5:]
        return meta.mtime_date is not None and meta.mtime_date.isoformat().startswith(wanted)
    return token.lower() in meta.name


def _rating_matches(path: str, expr: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    try:
        rating = int((user_setting_dict.get("image_ratings") or {}).get(path, 0))
    except (TypeError, ValueError):
        rating = 0
    for op in (">=", "<=", ">", "<"):
        if expr.startswith(op):
            try:
                target = int(expr[len(op):])
            except ValueError:
                return True
            return {
                ">=": rating >= target,
                "<=": rating <= target,
                ">": rating > target,
                "<": rating < target,
            }[op]
    try:
        return rating == int(expr)
    except ValueError:
        return True


def missing_paths(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if not Path(path).exists()]


def remove_missing(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if Path(path).exists()]


def auto_match_same_name(missing: Iterable[str], folder: str) -> dict[str, str]:
    """Pair missing paths with files of the same basename in *folder*."""
    root = Path(folder)
    if not root.is_dir():
        return {}
    by_name: dict[str, str] = {}
    for child in root.iterdir():
        if child.is_file():
            by_name.setdefault(child.name.lower(), str(child))
    return {
        old: by_name[Path(old).name.lower()]
        for old in missing
        if Path(old).name.lower() in by_name
    }


def relocate_root(paths: Iterable[str], old_root: str, new_root: str) -> dict[str, str]:
    """Map missing files from *old_root* to an equivalent path below *new_root*."""
    old_base = Path(old_root)
    new_base = Path(new_root)
    out: dict[str, str] = {}
    for raw in paths:
        path = Path(raw)
        try:
            rel = path.relative_to(old_base)
        except ValueError:
            rel = Path(path.name)
        candidate = new_base / rel
        if candidate.exists():
            out[raw] = str(candidate)
    return out


def detect_renamed_paths(old_paths: Iterable[str], new_paths: Iterable[str],
                         index: ImageMetadataIndex | None = None) -> dict[str, str]:
    """Infer same-file renames so thumbnail/metadata cache can migrate."""
    old_only = [p for p in old_paths if p not in new_paths]
    new_only = [p for p in new_paths if p not in old_paths]
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
        meta = index.get(path)
        if meta.size or meta.mtime_ns:
            return (meta.size, meta.mtime_ns, meta.suffix)
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns, Path(path).suffix.lower())


def _sample_hash(path: str, chunk: int = 64 * 1024) -> str:
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            head = fh.read(chunk)
            tail = b""
            if size > chunk:
                fh.seek(max(0, size - chunk))
                tail = fh.read(chunk)
    except OSError:
        return ""
    h = hashlib.sha256()
    h.update(str(size).encode())
    h.update(head)
    h.update(tail)
    return h.hexdigest()


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


def is_missing_file_error(message: str) -> bool:
    """FileNotFoundError-style messages → the quiet 'Missing' tile state.

    Distinguishes a vanished file (unplugged drive, deleted / moved image)
    from a genuine decode failure so the wall shows 'Missing' instead of a
    red 'Load failed' panel and skips the pointless retry."""
    text = (message or "").lower()
    return any(
        token in text
        for token in (
            "no such file or directory",
            "cannot find the file",
            "cannot find the path",
            "file not found",
            "does not exist",
        )
    )


def is_transient_load_error(message: str) -> bool:
    text = (message or "").lower()
    return any(
        token in text
        for token in (
            "being used",
            "locked",
            "permission",
            "temporarily",
            "resource busy",
            "busy",
            "access is denied",
            "cannot access",
        )
    )
