"""Writer transactions and nested committed reader snapshots."""
from __future__ import annotations

from functools import wraps
import contextlib
import sqlite3

from Imervue.library import index_connection as db


@contextlib.contextmanager
def write_batch():
    """Group many writes into a single transaction.

    The shared connection runs in autocommit mode, so without this each
    ``upsert_image`` is its own transaction — a bulk scan of N files becomes N
    commits. Wrapping a batch in one ``BEGIN`` … ``COMMIT`` collapses that into
    a single commit. The transaction is rolled back if the body raises, so a
    partially-applied chunk never lands.
    """
    # Hold the (reentrant) lock for the WHOLE transaction, not just BEGIN/COMMIT.
    # Releasing it during the body let a concurrent UI-thread write (set_cull_state
    # / add_image_tag, sharing this connection) execute INSIDE the scanner's open
    # transaction and get rolled back with it. The RLock lets the batch's own
    # upsert_image re-acquire on the same thread while blocking other threads.
    with db._lock:
        c = db.conn()
        c.execute("BEGIN")
        db._query_state.writing = True
        committed = False
        try:
            yield
            c.execute("COMMIT")
            committed = True
        finally:
            db._query_state.writing = False
            if not committed:
                c.execute("ROLLBACK")


def _query_connection() -> sqlite3.Connection:
    """The current snapshot, or the caller's serialized writer."""
    reader = getattr(db._query_state, "reader", None)
    return reader if reader is not None else db.conn()


def _inside_query() -> bool:
    """Whether this thread is already writing or reading under a snapshot."""
    return (getattr(db._query_state, "writing", False)
            or getattr(db._query_state, "reader", None) is not None)


def _on_snapshot(reader: sqlite3.Connection, call, transaction: bool):
    """Run *call* with *reader* as this thread's snapshot; the caller holds ``_read_lock``."""
    if transaction:
        reader.execute("BEGIN")
    db._query_state.reader = reader
    try:
        return call()
    finally:
        db._query_state.reader = None
        if transaction:
            reader.execute("ROLLBACK")  # ends snapshot, including error paths


def _read_snapshot(function, *, transaction: bool = False):
    """Eager query results under one reader lock; nested reads share a snapshot.

    Lock order is writer then reader for initialization/close. A reader never
    acquires the writer lock while holding its own lock. No cursor escapes.
    """
    @wraps(function)
    def read(*args, **kwargs):
        if _inside_query():
            return function(*args, **kwargs)
        while True:
            if db._reader is None:
                db.conn()  # initialize before acquiring _read_lock
            with db._read_lock:
                # None here: close/path switch won the initialization race, so retry.
                if db._reader is not None:
                    return _on_snapshot(
                        db._reader, lambda: function(*args, **kwargs), transaction)
    return read


def _read_transaction(function):
    """A shared snapshot for helpers that issue multiple queries."""
    return _read_snapshot(function, transaction=True)
