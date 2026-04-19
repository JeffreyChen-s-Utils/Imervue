"""
Library SQLite index — cross-folder image metadata, notes, hierarchical tags,
smart albums, perceptual hashes, and culling flags.

The DB lives at ``%LOCALAPPDATA%/Imervue/library.db`` (Windows) or
``~/.cache/imervue/library.db`` (POSIX). A single shared connection is used
with ``check_same_thread=False`` plus a process-wide lock, because SQLite's
own locking is fine for serialised writes and our throughput is very low.
WAL journal mode is enabled so readers don't block the background scanner.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
import threading
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

logger = logging.getLogger("Imervue.library")

_SCHEMA_VERSION = 1


def _default_db_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "library.db"
    return Path.home() / ".cache" / "imervue" / "library.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS images (
    path TEXT PRIMARY KEY,
    parent TEXT,
    name TEXT,
    ext TEXT,
    size INTEGER,
    mtime REAL,
    width INTEGER,
    height INTEGER,
    phash INTEGER,
    taken_at REAL,
    indexed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_images_parent ON images(parent);
CREATE INDEX IF NOT EXISTS idx_images_ext ON images(ext);
CREATE INDEX IF NOT EXISTS idx_images_taken_at ON images(taken_at);

CREATE TABLE IF NOT EXISTS notes (
    path TEXT PRIMARY KEY,
    note TEXT,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS tag_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    name TEXT NOT NULL,
    UNIQUE(parent_id, name)
);

CREATE TABLE IF NOT EXISTS image_tags (
    path TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (path, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id);

CREATE TABLE IF NOT EXISTS culling (
    path TEXT PRIMARY KEY,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS smart_albums (
    name TEXT PRIMARY KEY,
    rules_json TEXT NOT NULL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS library_roots (
    path TEXT PRIMARY KEY,
    added_at REAL
);
"""


# ---------------------------------------------------------------------------
# Connection / singleton
# ---------------------------------------------------------------------------

_conn: sqlite3.Connection | None = None
_db_path: Path | None = None
_lock = threading.RLock()


def set_db_path(path: Path | str) -> None:
    """Override the DB path — must be called before first ``conn()``. Test-only."""
    global _conn, _db_path
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        _db_path = Path(path)


def get_db_path() -> Path:
    global _db_path
    if _db_path is None:
        _db_path = _default_db_path()
    return _db_path


def conn() -> sqlite3.Connection:
    """Return the shared connection, creating and migrating the DB if needed."""
    global _conn
    with _lock:
        if _conn is not None:
            return _conn
        path = get_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA synchronous = NORMAL")
        c.execute("PRAGMA foreign_keys = ON")
        c.executescript(_SCHEMA_SQL)
        _set_schema_version(c, _SCHEMA_VERSION)
        _conn = c
        return c


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def _set_schema_version(c: sqlite3.Connection, version: int) -> None:
    c.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(version),),
    )


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def upsert_image(
    path: str,
    *,
    size: int | None = None,
    mtime: float | None = None,
    width: int | None = None,
    height: int | None = None,
    phash: int | None = None,
    taken_at: float | None = None,
) -> None:
    """Insert or update an image row. Unknown fields are left untouched on update."""
    p = Path(path)
    c = conn()
    now = time.time()
    with _lock:
        c.execute(
            "INSERT INTO images(path, parent, name, ext, size, mtime,"
            " width, height, phash, taken_at, indexed_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(path) DO UPDATE SET"
            " parent=excluded.parent, name=excluded.name, ext=excluded.ext,"
            " size=COALESCE(excluded.size, images.size),"
            " mtime=COALESCE(excluded.mtime, images.mtime),"
            " width=COALESCE(excluded.width, images.width),"
            " height=COALESCE(excluded.height, images.height),"
            " phash=COALESCE(excluded.phash, images.phash),"
            " taken_at=COALESCE(excluded.taken_at, images.taken_at),"
            " indexed_at=excluded.indexed_at",
            (
                str(p), str(p.parent), p.name, p.suffix.lower().lstrip("."),
                size, mtime, width, height, phash, taken_at, now,
            ),
        )


def get_image(path: str) -> dict | None:
    row = conn().execute(
        "SELECT * FROM images WHERE path = ?", (str(path),)
    ).fetchone()
    return dict(row) if row else None


def delete_image(path: str) -> None:
    with _lock:
        c = conn()
        c.execute("DELETE FROM images WHERE path = ?", (str(path),))
        c.execute("DELETE FROM notes WHERE path = ?", (str(path),))
        c.execute("DELETE FROM culling WHERE path = ?", (str(path),))
        c.execute("DELETE FROM image_tags WHERE path = ?", (str(path),))


def all_image_paths() -> list[str]:
    return [r["path"] for r in conn().execute("SELECT path FROM images").fetchall()]


def count_images() -> int:
    return conn().execute("SELECT COUNT(*) AS n FROM images").fetchone()["n"]


def search_images(
    *,
    parents: Sequence[str] | None = None,
    exts: Sequence[str] | None = None,
    min_width: int | None = None,
    min_height: int | None = None,
    max_size: int | None = None,
    min_size: int | None = None,
    name_contains: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Run a parameterised search over the index — returns matching paths."""
    where: list[str] = []
    args: list = []
    if parents:
        placeholders = ",".join("?" * len(parents))
        where.append(f"parent IN ({placeholders})")
        args.extend(parents)
    if exts:
        placeholders = ",".join("?" * len(exts))
        where.append(f"ext IN ({placeholders})")
        args.extend(e.lower().lstrip(".") for e in exts)
    if min_width is not None:
        where.append("width >= ?")
        args.append(min_width)
    if min_height is not None:
        where.append("height >= ?")
        args.append(min_height)
    if min_size is not None:
        where.append("size >= ?")
        args.append(min_size)
    if max_size is not None:
        where.append("size <= ?")
        args.append(max_size)
    if name_contains:
        where.append("LOWER(name) LIKE ?")
        args.append(f"%{name_contains.lower()}%")

    sql = "SELECT path FROM images"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY taken_at DESC, mtime DESC"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"  # nosec B608 - limit is int-coerced above
    return [r["path"] for r in conn().execute(sql, args).fetchall()]  # nosec B608


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def set_note(path: str, note: str) -> None:
    with _lock:
        c = conn()
        if not note:
            c.execute("DELETE FROM notes WHERE path = ?", (str(path),))
            return
        c.execute(
            "INSERT INTO notes(path, note, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(path) DO UPDATE SET note=excluded.note,"
            " updated_at=excluded.updated_at",
            (str(path), note, time.time()),
        )


def get_note(path: str) -> str:
    row = conn().execute(
        "SELECT note FROM notes WHERE path = ?", (str(path),)
    ).fetchone()
    return row["note"] if row else ""


def paths_with_notes() -> list[str]:
    return [r["path"] for r in conn().execute(
        "SELECT path FROM notes WHERE COALESCE(note, '') <> ''"
    ).fetchall()]


# ---------------------------------------------------------------------------
# Hierarchical tags
# ---------------------------------------------------------------------------


def _tag_id(path_parts: Sequence[str], create: bool) -> int | None:
    """Resolve ``a/b/c`` to a tag_nodes.id, creating rows along the way if asked."""
    c = conn()
    parent_id: int | None = None
    for name in path_parts:
        row = c.execute(
            "SELECT id FROM tag_nodes WHERE parent_id IS ? AND name = ?",
            (parent_id, name),
        ).fetchone()
        if row is None:
            if not create:
                return None
            cur = c.execute(
                "INSERT INTO tag_nodes(parent_id, name) VALUES(?, ?)",
                (parent_id, name),
            )
            parent_id = cur.lastrowid
        else:
            parent_id = row["id"]
    return parent_id


def create_tag_path(tag_path: str) -> int:
    """Ensure a hierarchical tag like ``animal/cat/british`` exists; return its id."""
    parts = [s.strip() for s in tag_path.split("/") if s.strip()]
    if not parts:
        raise ValueError("empty tag path")
    with _lock:
        tid = _tag_id(parts, create=True)
        if tid is None:
            raise RuntimeError("failed to create tag path")
        return tid


def delete_tag_path(tag_path: str) -> bool:
    parts = [s.strip() for s in tag_path.split("/") if s.strip()]
    if not parts:
        return False
    with _lock:
        tid = _tag_id(parts, create=False)
        if tid is None:
            return False
        c = conn()
        # Remove the node and all descendants (recursive), plus links.
        descendant_ids = _descendants_of(tid)
        descendant_ids.append(tid)
        placeholders = ",".join("?" * len(descendant_ids))
        c.execute(
            f"DELETE FROM image_tags WHERE tag_id IN ({placeholders})",  # noqa: S608  # nosec B608
            descendant_ids,
        )
        c.execute(
            f"DELETE FROM tag_nodes WHERE id IN ({placeholders})",  # noqa: S608  # nosec B608
            descendant_ids,
        )
        return True


def _descendants_of(tag_id: int) -> list[int]:
    out: list[int] = []
    frontier = [tag_id]
    c = conn()
    while frontier:
        placeholders = ",".join("?" * len(frontier))
        rows = c.execute(
            f"SELECT id FROM tag_nodes WHERE parent_id IN ({placeholders})",  # noqa: S608  # nosec B608
            frontier,
        ).fetchall()
        next_frontier = [r["id"] for r in rows]
        out.extend(next_frontier)
        frontier = next_frontier
    return out


def tag_path_of(tag_id: int) -> str:
    """Return dotted path like ``animal/cat/british`` for a tag id."""
    c = conn()
    parts: list[str] = []
    current: int | None = tag_id
    while current is not None:
        row = c.execute(
            "SELECT name, parent_id FROM tag_nodes WHERE id = ?", (current,)
        ).fetchone()
        if row is None:
            break
        parts.append(row["name"])
        current = row["parent_id"]
    parts.reverse()
    return "/".join(parts)


def all_tag_paths() -> list[str]:
    c = conn()
    rows = c.execute("SELECT id FROM tag_nodes").fetchall()
    return sorted(tag_path_of(r["id"]) for r in rows)


def add_image_tag(path: str, tag_path: str) -> None:
    with _lock:
        tid = create_tag_path(tag_path)
        conn().execute(
            "INSERT OR IGNORE INTO image_tags(path, tag_id) VALUES(?, ?)",
            (str(path), tid),
        )


def remove_image_tag(path: str, tag_path: str) -> bool:
    parts = [s.strip() for s in tag_path.split("/") if s.strip()]
    if not parts:
        return False
    with _lock:
        tid = _tag_id(parts, create=False)
        if tid is None:
            return False
        cur = conn().execute(
            "DELETE FROM image_tags WHERE path = ? AND tag_id = ?",
            (str(path), tid),
        )
        return cur.rowcount > 0


def tags_of_image(path: str) -> list[str]:
    rows = conn().execute(
        "SELECT tag_id FROM image_tags WHERE path = ?", (str(path),)
    ).fetchall()
    return sorted(tag_path_of(r["tag_id"]) for r in rows)


def images_with_tag(tag_path: str, *, include_descendants: bool = True) -> list[str]:
    parts = [s.strip() for s in tag_path.split("/") if s.strip()]
    if not parts:
        return []
    tid = _tag_id(parts, create=False)
    if tid is None:
        return []
    ids = [tid] + (_descendants_of(tid) if include_descendants else [])
    placeholders = ",".join("?" * len(ids))
    rows = conn().execute(
        f"SELECT DISTINCT path FROM image_tags WHERE tag_id IN ({placeholders})",  # noqa: S608  # nosec B608
        ids,
    ).fetchall()
    return sorted(r["path"] for r in rows)


# ---------------------------------------------------------------------------
# Culling (Pick / Reject)
# ---------------------------------------------------------------------------

CULL_PICK = "pick"
CULL_REJECT = "reject"
CULL_UNFLAGGED = "unflagged"
_VALID_CULL = {CULL_PICK, CULL_REJECT, CULL_UNFLAGGED}


def set_cull_state(path: str, state: str) -> None:
    if state not in _VALID_CULL:
        raise ValueError(f"invalid culling state: {state}")
    with _lock:
        c = conn()
        if state == CULL_UNFLAGGED:
            c.execute("DELETE FROM culling WHERE path = ?", (str(path),))
            return
        c.execute(
            "INSERT INTO culling(path, state) VALUES(?, ?)"
            " ON CONFLICT(path) DO UPDATE SET state=excluded.state",
            (str(path), state),
        )


def get_cull_state(path: str) -> str:
    row = conn().execute(
        "SELECT state FROM culling WHERE path = ?", (str(path),)
    ).fetchone()
    return row["state"] if row else CULL_UNFLAGGED


def paths_with_cull_state(state: str) -> list[str]:
    if state == CULL_UNFLAGGED:
        return []
    rows = conn().execute(
        "SELECT path FROM culling WHERE state = ?", (state,)
    ).fetchall()
    return [r["path"] for r in rows]


def filter_by_cull(paths: Iterable[str], state: str | None) -> list[str]:
    """Filter an image list by cull state; None means no filter."""
    paths = list(paths)
    if not state:
        return paths
    rows = conn().execute("SELECT path, state FROM culling").fetchall()
    states = {r["path"]: r["state"] for r in rows}
    if state == CULL_UNFLAGGED:
        return [p for p in paths if p not in states]
    return [p for p in paths if states.get(p) == state]


# ---------------------------------------------------------------------------
# Smart albums (saved searches)
# ---------------------------------------------------------------------------


def save_smart_album(name: str, rules_json: str) -> None:
    with _lock:
        conn().execute(
            "INSERT INTO smart_albums(name, rules_json, updated_at) VALUES(?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET rules_json=excluded.rules_json,"
            " updated_at=excluded.updated_at",
            (name, rules_json, time.time()),
        )


def delete_smart_album(name: str) -> bool:
    with _lock:
        cur = conn().execute("DELETE FROM smart_albums WHERE name = ?", (name,))
        return cur.rowcount > 0


def list_smart_albums() -> list[dict]:
    rows = conn().execute(
        "SELECT name, rules_json, updated_at FROM smart_albums"
        " ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


def get_smart_album(name: str) -> dict | None:
    row = conn().execute(
        "SELECT name, rules_json, updated_at FROM smart_albums WHERE name = ?",
        (name,),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Library roots
# ---------------------------------------------------------------------------


def add_library_root(path: str) -> None:
    with _lock:
        conn().execute(
            "INSERT OR IGNORE INTO library_roots(path, added_at) VALUES(?, ?)",
            (str(path), time.time()),
        )


def remove_library_root(path: str) -> bool:
    with _lock:
        cur = conn().execute("DELETE FROM library_roots WHERE path = ?", (str(path),))
        return cur.rowcount > 0


def list_library_roots() -> list[str]:
    rows = conn().execute("SELECT path FROM library_roots ORDER BY path").fetchall()
    return [r["path"] for r in rows]


# ---------------------------------------------------------------------------
# pHash similarity
# ---------------------------------------------------------------------------


def similar_by_phash(phash: int, max_distance: int = 10, limit: int = 100) -> list[tuple[str, int]]:
    """Return (path, hamming_distance) rows with phash within ``max_distance`` bits.

    Brute-force scan — fine up to tens of thousands of images; beyond that we'd
    need a BK-tree. Returns sorted closest-first.
    """
    rows = conn().execute(
        "SELECT path, phash FROM images WHERE phash IS NOT NULL"
    ).fetchall()
    out: list[tuple[str, int]] = []
    for r in rows:
        other = r["phash"]
        if other is None:
            continue
        dist = bin(int(phash) ^ int(other)).count("1")
        if dist <= max_distance:
            out.append((r["path"], dist))
    out.sort(key=lambda x: x[1])
    return out[:limit]
