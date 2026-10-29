"""Cached current and legacy content identities for recipe persistence."""

from __future__ import annotations

import hashlib
from pathlib import Path

_IDENTITY_CHUNK = 4096
_IDENTITY_SALT = b"imervue-identity-2"
_IDENTITY_CACHE: dict[str, tuple[int, int, str, str]] = {}


def _identity_chunks(path: Path, size: int) -> tuple[bytes, bytes, bytes]:
    """The first, middle and last :data:`_IDENTITY_CHUNK` bytes of *path*."""
    with open(path, "rb") as f:
        head = f.read(_IDENTITY_CHUNK)
        f.seek(max(0, size // 2 - _IDENTITY_CHUNK // 2))
        middle = f.read(_IDENTITY_CHUNK)
        f.seek(max(0, size - _IDENTITY_CHUNK))
        tail = f.read(_IDENTITY_CHUNK)
    return head, middle, tail


def file_identities(path: str | Path) -> tuple[str, str]:
    """``(identity, pre-2 identity)`` of *path*; ``("", "")`` when it can't be read.

    The pre-2 identity (md5 of the first 4 KB and the size) is what recipes
    were stored under before; ``recipe_store`` moves such an entry to the
    current identity the first time the file is looked up.
    """
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return "", ""
    key = str(p)
    cached = _IDENTITY_CACHE.get(key)
    if cached is not None and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
        return cached[2], cached[3]
    try:
        head, middle, tail = _identity_chunks(p, st.st_size)
    except OSError:
        return "", ""
    size = st.st_size.to_bytes(8, "big")
    identity = hashlib.md5(
        _IDENTITY_SALT + head + middle + tail + size, usedforsecurity=False
    ).hexdigest()
    legacy = hashlib.md5(head + size, usedforsecurity=False).hexdigest()
    _IDENTITY_CACHE[key] = (st.st_mtime_ns, st.st_size, identity, legacy)
    return identity, legacy


def file_identity(path: str | Path) -> str:
    """Stable per-content identity: md5 of the first, middle and last 4 KB and the file size.

    A pure mtime/path key would invalidate on every touch (backup tools, a
    copy, a rename), so the identity comes from the bytes. The first 4 KB
    alone were not enough: two scanned pages of one size in an uncompressed
    format (BMP, TIFF) share their header, their white top rows and their
    size, so every page showed the one recipe. The middle and the end of the
    file tell them apart. The first bytes hold a JPEG's EXIF, so a metadata
    rewrite or a lossless rotate changes the identity: Imervue's own rewrites
    carry the recipe over with ``recipe_store.carry_recipe``.

    Results are cached in-process keyed by (mtime_ns, size) so repeated
    lookups during the same session are effectively free.
    """
    return file_identities(path)[0]


def clear_identity_cache() -> None:
    """Drop the in-process identity cache. Used by tests."""
    _IDENTITY_CACHE.clear()
