"""Per-image notes and their update timestamps."""
from __future__ import annotations

import time

from Imervue.library import index_connection as db
from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_snapshot


def set_note(path: str, note: str) -> None:
    with db._lock:
        c = db.conn()
        if not note:
            c.execute("DELETE FROM notes WHERE path = ?", (str(path),))
            return
        c.execute(
            "INSERT INTO notes(path, note, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(path) DO UPDATE SET note=excluded.note,"
            " updated_at=excluded.updated_at",
            (str(path), note, time.time()),
        )


@_read_snapshot
def get_note(path: str) -> str:
    row = _query_connection().execute(
        "SELECT note FROM notes WHERE path = ?", (str(path),)
    ).fetchone()
    return row["note"] if row else ""


@_read_snapshot
def paths_with_notes() -> list[str]:
    return [r["path"] for r in _query_connection().execute(
        "SELECT path FROM notes WHERE COALESCE(note, '') <> ''"
    ).fetchall()]
