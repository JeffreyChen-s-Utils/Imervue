"""Hierarchical tag parsing, node identity and deletion."""
from __future__ import annotations

from collections.abc import Sequence

from Imervue.library import index_connection as db
from Imervue.library.index_snapshot import _query_connection


def _tag_parts(tag_path: str) -> list[str]:
    return [part.strip() for part in tag_path.split("/") if part.strip()]


def _tag_id(path_parts: Sequence[str], create: bool) -> int | None:
    """Resolve ``a/b/c`` to a tag_nodes.id, creating rows along the way if asked."""
    c = _query_connection()
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
    parts = _tag_parts(tag_path)
    if not parts:
        raise ValueError("empty tag path")
    with db._lock:
        tid = _tag_id(parts, create=True)
        if tid is None:
            raise RuntimeError("failed to create tag path")
        return tid


def delete_tag_path(tag_path: str) -> bool:
    parts = _tag_parts(tag_path)
    if not parts:
        return False
    with db._lock:
        tid = _tag_id(parts, create=False)
        if tid is None:
            return False
        c = db.conn()
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
    c = _query_connection()
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
