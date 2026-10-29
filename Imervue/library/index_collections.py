"""Saved search definitions and library root persistence."""
from __future__ import annotations

import time

from Imervue.library import index_connection as db
from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_snapshot


def save_smart_album(name: str, rules_json: str) -> None:
    with db._lock:
        db.conn().execute(
            "INSERT INTO smart_albums(name, rules_json, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET rules_json=excluded.rules_json,"
            " updated_at=excluded.updated_at",
            (name, rules_json, time.time()),
        )


def delete_smart_album(name: str) -> bool:
    with db._lock:
        cur = db.conn().execute("DELETE FROM smart_albums WHERE name = ?", (name,))
        return cur.rowcount > 0


@_read_snapshot
def list_smart_albums() -> list[dict]:
    rows = _query_connection().execute(
        "SELECT name, rules_json, updated_at FROM smart_albums"
        " ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


@_read_snapshot
def get_smart_album(name: str) -> dict | None:
    row = _query_connection().execute(
        "SELECT name, rules_json, updated_at FROM smart_albums WHERE name = ?",
        (name,),
    ).fetchone()
    return dict(row) if row else None


def add_library_root(path: str) -> None:
    with db._lock:
        db.conn().execute(
            "INSERT OR IGNORE INTO library_roots(path, added_at) VALUES(?, ?)",
            (str(path), time.time()),
        )


def remove_library_root(path: str) -> bool:
    with db._lock:
        cur = db.conn().execute("DELETE FROM library_roots WHERE path = ?", (str(path),))
        return cur.rowcount > 0


@_read_snapshot
def list_library_roots() -> list[str]:
    rows = _query_connection().execute("SELECT path FROM library_roots ORDER BY path").fetchall()
    return [r["path"] for r in rows]
