"""Transactional relocation of image-associated rows."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sqlite3

from Imervue.library import index_connection as db
from Imervue.library.index_connection import library_exists
from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_snapshot
from Imervue.library.index_snapshot import write_batch


_PATH_TABLES = ("images", "notes", "culling", "image_tags")


# Rows are parked under this prefix mid-move, so ``a -> b`` beside ``b -> c``
# moves each once. SQLite's substr() stops at a NUL, hence \u0001.
_MOVING = "\u0001moving\u0001"


def _move_rows(c: sqlite3.Connection, table: str, pairs: dict[str, str], *,
               keep_existing: bool) -> None:
    for old, new in pairs.items():
        if keep_existing and c.execute(
                f"SELECT 1 FROM {table} WHERE path = ? LIMIT 1",  # noqa: S608  # nosec B608  # table from _PATH_TABLES
                (new,)).fetchone():
            continue
        c.execute(f"UPDATE {table} SET path = ? WHERE path = ?",  # noqa: S608  # nosec B608  # table from _PATH_TABLES
                  (_MOVING + new, old))
    if not keep_existing:        # rows of a file that used to live at a new path
        c.executemany(f"DELETE FROM {table} WHERE path = ?",  # noqa: S608  # nosec B608  # table from _PATH_TABLES
                      [(new,) for new in pairs.values() if new not in pairs])
    c.execute(f"UPDATE {table} SET path = substr(path, ?) WHERE substr(path, 1, ?) = ?",  # noqa: S608  # nosec B608  # table from _PATH_TABLES
              (len(_MOVING) + 1, len(_MOVING), _MOVING))


def move_paths(mapping: Mapping[str, str], *, keep_existing: bool = False) -> None:
    """Re-key each old path's rows to its new path: index entry, note, cull state and tags.

    For files Imervue renamed or moved, so a new path had no file of its own
    a moment ago: rows found under one belonged to a file that used to live
    there and are dropped. With *keep_existing* (relinking missing files) a
    table that already has rows for a new path keeps them and leaves the old
    rows alone. All in one transaction; nothing happens when the library was
    never opened (no DB file is created for it).
    """
    pairs = {str(old): str(new) for old, new in mapping.items() if str(old) != str(new)}
    if not pairs or not library_exists():
        return
    with write_batch():
        c = db.conn()
        for table in _PATH_TABLES:
            _move_rows(c, table, pairs, keep_existing=keep_existing)
        c.executemany(
            "UPDATE images SET parent = ?, name = ?, ext = ? WHERE path = ?",
            [(str(Path(new).parent), Path(new).name, Path(new).suffix.lower().lstrip("."), new)
             for new in pairs.values()],
        )


def stored_paths() -> list[str]:
    """Every distinct image path any table keeps rows for; empty without a library."""
    if not library_exists():
        return []
    return _stored_paths()


@_read_snapshot
def _stored_paths() -> list[str]:
    rows = _query_connection().execute(
        " UNION ".join(f"SELECT path FROM {table}"  # noqa: S608  # nosec B608  # table from _PATH_TABLES
                       for table in _PATH_TABLES)).fetchall()
    return [row["path"] for row in rows]
