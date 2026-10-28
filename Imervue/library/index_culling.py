"""Pick/reject persistence and ordered image filtering."""
from __future__ import annotations

from collections.abc import Iterable

from Imervue.library import index_connection as db
from Imervue.library.index_snapshot import _query_connection
from Imervue.library.index_snapshot import _read_snapshot


CULL_PICK = "pick"


CULL_REJECT = "reject"


CULL_UNFLAGGED = "unflagged"


_VALID_CULL = {CULL_PICK, CULL_REJECT, CULL_UNFLAGGED}


def set_cull_state(path: str, state: str) -> None:
    if state not in _VALID_CULL:
        raise ValueError(f"invalid culling state: {state}")
    with db._lock:
        c = db.conn()
        if state == CULL_UNFLAGGED:
            c.execute("DELETE FROM culling WHERE path = ?", (str(path),))
            return
        c.execute(
            "INSERT INTO culling(path, state) VALUES(?, ?)"
            " ON CONFLICT(path) DO UPDATE SET state=excluded.state",
            (str(path), state),
        )


@_read_snapshot
def get_cull_state(path: str) -> str:
    row = _query_connection().execute(
        "SELECT state FROM culling WHERE path = ?", (str(path),)
    ).fetchone()
    return row["state"] if row else CULL_UNFLAGGED


@_read_snapshot
def paths_with_cull_state(state: str) -> list[str]:
    if state == CULL_UNFLAGGED:
        return []
    rows = _query_connection().execute(
        "SELECT path FROM culling WHERE state = ?", (state,)
    ).fetchall()
    return [r["path"] for r in rows]


@_read_snapshot
def filter_by_cull(paths: Iterable[str], state: str | None) -> list[str]:
    """Filter an image list by cull state; None means no filter."""
    paths = list(paths)
    if not state:
        return paths
    rows = _query_connection().execute("SELECT path, state FROM culling").fetchall()
    states = {r["path"]: r["state"] for r in rows}
    if state == CULL_UNFLAGGED:
        return [p for p in paths if p not in states]
    return [p for p in paths if states.get(p) == state]
