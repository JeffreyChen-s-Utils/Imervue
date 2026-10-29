"""Stat-backed image metadata cache for one browsing session.

``ImageMetadataIndex`` memoises file attributes (and, on demand, image
dimensions) plus a sampled content hash, skipping transient stat failures so
a locked or mid-move file is re-read later instead of sticking as a sentinel.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path


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
        self._stat_items: dict[str, ImageMeta] = {}
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
            self._stat_items.pop(path, None)
        return meta

    def peek(self, path: str) -> ImageMeta | None:
        """Return already cached metadata without opening or stat-ing a file."""
        return self._items.get(path) or self._stat_items.get(path)

    def get_stat(self, path: str) -> ImageMeta:
        """Read file attributes only; filtering and rename matching need no image headers."""
        meta = self.peek(path)
        if meta is not None:
            return meta
        meta, cacheable = self._read(path, with_dimensions=False)
        if cacheable:
            self._stat_items[path] = meta
        return meta

    def prime(self, paths: Iterable[str], *, limit: int | None = None) -> None:
        for i, path in enumerate(paths):
            if limit is not None and i >= limit:
                break
            self.get_stat(path)

    def drop_missing(self) -> None:
        for path in [p for p in self._items.keys() | self._stat_items.keys()
                     if not Path(p).exists()]:
            self._items.pop(path, None)
            self._stat_items.pop(path, None)

    def move(self, old_path: str, new_path: str) -> None:
        meta = self._items.pop(old_path, None)
        stat_meta = self._stat_items.pop(old_path, None)
        if meta is not None:
            # Mirror get(): don't cache a transient stat-failure sentinel for the
            # rename target (mid-move / AV-locked) — re-read next time instead of
            # dropping it from the date/size filters for the session.
            new_meta, cacheable = self._read(new_path)
            if cacheable:
                self._items[new_path] = new_meta
        elif stat_meta is not None:
            new_meta, cacheable = self._read(new_path, with_dimensions=False)
            if cacheable:
                self._stat_items[new_path] = new_meta
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
    def _read(path: str, *, with_dimensions: bool = True) -> tuple[ImageMeta, bool]:
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
        if size and with_dimensions:
            from Imervue.image.dimensions import image_dimensions
            # Not a readable image: the dimensions stay unknown.
            width, height = image_dimensions(path) or (None, None)
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

