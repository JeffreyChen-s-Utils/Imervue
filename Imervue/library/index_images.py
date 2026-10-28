"""Catalog image fields and bounded fingerprint enumeration."""
from __future__ import annotations

from pathlib import Path
import time

from Imervue.library import index_connection as db
from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_snapshot
from Imervue.library.phash import to_signed64


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
    now = time.time()
    # A 64-bit pHash is unsigned and routinely has its high bit set, which
    # overflows SQLite's signed INTEGER; store the identical bits as signed.
    stored_phash = to_signed64(phash) if phash is not None else None
    with db._lock:
        c = db.conn()
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
                size, mtime, width, height, stored_phash, taken_at, now,
            ),
        )


def set_decoded_fields(
    path: str, *, width: int | None, height: int | None, phash: int | None,
) -> None:
    """Replace the fields read from the file's pixels; ``None`` clears one.

    Unlike :func:`upsert_image`, which keeps an old value where the new one is
    ``None``, this makes a rescanned file's size and pHash describe its current
    content, or nothing when it was not read or could not be.
    """
    stored_phash = to_signed64(phash) if phash is not None else None
    with db._lock:
        db.conn().execute(
            "UPDATE images SET width = ?, height = ?, phash = ? WHERE path = ?",
            (width, height, stored_phash, str(path)),
        )


@_read_snapshot
def get_image(path: str) -> dict | None:
    row = _query_connection().execute(
        "SELECT * FROM images WHERE path = ?", (str(path),)
    ).fetchone()
    return dict(row) if row else None


def delete_image(path: str) -> None:
    with db._lock:
        c = db.conn()
        c.execute("DELETE FROM images WHERE path = ?", (str(path),))
        c.execute("DELETE FROM notes WHERE path = ?", (str(path),))
        c.execute("DELETE FROM culling WHERE path = ?", (str(path),))
        c.execute("DELETE FROM image_tags WHERE path = ?", (str(path),))


@_read_snapshot
def all_image_paths() -> list[str]:
    return [r["path"] for r in _query_connection().execute("SELECT path FROM images").fetchall()]


@_read_snapshot
def _fingerprint_page(after: str | None):
    sql = "SELECT path, mtime, size FROM images WHERE mtime IS NOT NULL AND size IS NOT NULL"
    args = ()
    if after is not None:
        sql += " AND path > ?"
        args = (after,)
    return _query_connection().execute(sql + " ORDER BY path LIMIT 1000", args).fetchall()


def iter_image_fingerprints():
    """Yield fingerprints in bounded pages, releasing the reader between pages.

    Each page is a committed snapshot. Concurrent changes can cause an extra
    filesystem rescan, but cannot leak a cursor or pin the WAL during yielding.
    """
    after = None
    while rows := _fingerprint_page(after):
        for row in rows:
            yield row["path"], float(row["mtime"]), int(row["size"])
        after = rows[-1]["path"]


@_read_snapshot
def count_images() -> int:
    return _query_connection().execute("SELECT COUNT(*) AS n FROM images").fetchone()["n"]
