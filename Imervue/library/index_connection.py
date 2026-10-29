"""Canonical catalog connections, locks, path and lifecycle."""
from __future__ import annotations

from pathlib import Path
import contextlib
import os
import sqlite3
import sys
import threading

from Imervue.library.index_schema import _SCHEMA_SQL
from Imervue.library.index_schema import _SCHEMA_VERSION
from Imervue.library.index_schema import _set_schema_version


def _default_db_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "library.db"
    return Path.home() / ".cache" / "imervue" / "library.db"


_conn: sqlite3.Connection | None = None
_db_path: Path | None = None
_lock = threading.RLock()
_read_lock = threading.RLock()
_reader: sqlite3.Connection | None = None
_query_state = threading.local()


def set_db_path(path: Path | str) -> None:
    """Override the DB path — must be called before first ``conn()``. Test-only."""
    global _db_path
    with _lock:
        close()
        _db_path = Path(path)


def get_db_path() -> Path:
    global _db_path
    if _db_path is None:
        _db_path = _default_db_path()
    return _db_path


def conn() -> sqlite3.Connection:
    """Return the shared connection, creating and migrating the DB if needed."""
    global _conn, _reader
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
        try:
            with _read_lock:
                _reader = _open_reader(path)
                _conn = c
        except sqlite3.Error:
            c.close()
            raise
        return c


def _open_reader(path: Path) -> sqlite3.Connection:
    reader = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    try:
        reader.row_factory = sqlite3.Row
        reader.execute("PRAGMA query_only = ON")
        return reader
    except sqlite3.Error:
        reader.close()
        raise


def close() -> None:
    global _conn, _reader
    with _lock, _read_lock:
        if _reader is not None:
            _reader.close()
            _reader = None
        if _conn is not None:
            # Hand SQLite a chance to update query-plan statistics
            # before we drop the connection. ``PRAGMA optimize`` is
            # the recommended on-close hook (since SQLite 3.18) —
            # cheap when nothing's changed, applies an ANALYZE when
            # tables have grown enough that the plan would shift.
            with contextlib.suppress(sqlite3.Error):
                _conn.execute("PRAGMA optimize")
            _conn.close()
            _conn = None


def library_exists() -> bool:
    """Whether the library DB is open or on disk — a rename or a read must not create one."""
    return _conn is not None or get_db_path().exists()
