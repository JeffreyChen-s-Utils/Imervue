"""Image filters and perceptual-hash similarity queries."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_snapshot
from Imervue.library.phash import hamming


@dataclass(frozen=True)
class ImageQuery:
    """Filters for :func:`search_images`; a ``None`` / empty field leaves that filter off.

    Sizes are in bytes, dimensions in pixels; ``exts`` match without the dot
    and case-insensitively, ``name_contains`` case-insensitively.
    """

    parents: Sequence[str] | None = None
    exts: Sequence[str] | None = None
    min_width: int | None = None
    min_height: int | None = None
    max_size: int | None = None
    min_size: int | None = None
    name_contains: str | None = None
    limit: int | None = None


def _query_where(query: ImageQuery) -> tuple[list[str], list]:
    """SQL ``WHERE`` terms and their bound values for ``query``."""
    where: list[str] = []
    args: list = []
    if query.parents:
        where.append(f"parent IN ({','.join('?' * len(query.parents))})")
        args.extend(query.parents)
    if query.exts:
        where.append(f"ext IN ({','.join('?' * len(query.exts))})")
        args.extend(e.lower().lstrip(".") for e in query.exts)
    for value, term in ((query.min_width, "width >= ?"), (query.min_height, "height >= ?"),
                        (query.min_size, "size >= ?"), (query.max_size, "size <= ?")):
        if value is not None:
            where.append(term)
            args.append(value)
    if query.name_contains:
        where.append("LOWER(name) LIKE ?")
        args.append(f"%{query.name_contains.lower()}%")
    return where, args


@_read_snapshot
def search_images(query: ImageQuery | None = None) -> list[str]:
    """Run a parameterised search over the index — returns matching paths, newest first."""
    query = query or ImageQuery()
    where, args = _query_where(query)
    sql = "SELECT path FROM images"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY taken_at DESC, mtime DESC"
    if query.limit is not None:
        sql += f" LIMIT {int(query.limit)}"  # nosec B608 - limit is int-coerced above
    return [r["path"] for r in _query_connection().execute(sql, args).fetchall()]  # nosec B608


@_read_snapshot
def similar_by_phash(phash: int, max_distance: int = 10, limit: int = 100) -> list[tuple[str, int]]:
    """Return (path, hamming_distance) rows with phash within ``max_distance`` bits.

    Brute-force scan — fine up to tens of thousands of images; beyond that we'd
    need a BK-tree. Returns sorted closest-first.
    """
    rows = _query_connection().execute(
        "SELECT path, phash FROM images WHERE phash IS NOT NULL"
    ).fetchall()
    out: list[tuple[str, int]] = []
    for r in rows:
        other = r["phash"]
        if other is None:
            continue
        # ``phash`` may be an in-memory unsigned hash and ``other`` the signed
        # value read back from SQLite; ``hamming`` masks both to 64 bits so the
        # two representations of the same pattern compare identically.
        dist = hamming(phash, other)
        if dist <= max_distance:
            out.append((r["path"], dist))
    out.sort(key=lambda x: x[1])
    return out[:limit]
