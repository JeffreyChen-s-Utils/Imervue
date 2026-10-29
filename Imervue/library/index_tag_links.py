"""Image-tag assignments and snapshot-consistent tag queries."""
from __future__ import annotations

from Imervue.library import index_connection as db
from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_transaction
from Imervue.library.index_tags import _descendants_of
from Imervue.library.index_tags import _tag_id
from Imervue.library.index_tags import _tag_parts
from Imervue.library.index_tags import create_tag_path


@_read_transaction
def tag_path_of(tag_id: int) -> str:
    """Return dotted path like ``animal/cat/british`` for a tag id."""
    c = _query_connection()
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


@_read_transaction
def all_tag_paths() -> list[str]:
    c = _query_connection()
    rows = c.execute("SELECT id FROM tag_nodes").fetchall()
    return sorted(tag_path_of(r["id"]) for r in rows)


def add_image_tag(path: str, tag_path: str) -> None:
    with db._lock:
        tid = create_tag_path(tag_path)
        db.conn().execute(
            "INSERT OR IGNORE INTO image_tags(path, tag_id) VALUES(?, ?)",
            (str(path), tid),
        )


def remove_image_tag(path: str, tag_path: str) -> bool:
    parts = _tag_parts(tag_path)
    if not parts:
        return False
    with db._lock:
        tid = _tag_id(parts, create=False)
        if tid is None:
            return False
        cur = db.conn().execute(
            "DELETE FROM image_tags WHERE path = ? AND tag_id = ?",
            (str(path), tid),
        )
        return cur.rowcount > 0


@_read_transaction
def tags_of_image(path: str) -> list[str]:
    rows = _query_connection().execute(
        "SELECT tag_id FROM image_tags WHERE path = ?", (str(path),)
    ).fetchall()
    return sorted(tag_path_of(r["tag_id"]) for r in rows)


@_read_transaction
def images_with_tag(tag_path: str, *, include_descendants: bool = True) -> list[str]:
    parts = _tag_parts(tag_path)
    if not parts:
        return []
    tid = _tag_id(parts, create=False)
    if tid is None:
        return []
    ids = [tid] + (_descendants_of(tid) if include_descendants else [])
    placeholders = ",".join("?" * len(ids))
    rows = _query_connection().execute(
        f"SELECT DISTINCT path FROM image_tags WHERE tag_id IN ({placeholders})",  # noqa: S608  # nosec B608
        ids,
    ).fetchall()
    return sorted(r["path"] for r in rows)
