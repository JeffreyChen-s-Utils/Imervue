"""write_batch must hold the lock for its whole body, not just BEGIN/COMMIT.

Releasing it during the transaction let a concurrent UI-thread write (sharing the
connection) execute inside the scanner's open transaction and be rolled back with
it. The reentrant lock is now held across the entire body.
"""
from __future__ import annotations

import threading

import pytest

from Imervue.library import image_index


class _StubConn:
    def execute(self, _sql):   # noqa: D401 - stub
        return None


def test_lock_is_held_across_the_whole_body(monkeypatch):
    monkeypatch.setattr(image_index, "conn", lambda: _StubConn())
    other_thread_got_lock: list = []

    def _try_acquire():
        got = image_index._lock.acquire(blocking=False)
        other_thread_got_lock.append(got)
        if got:
            image_index._lock.release()

    with image_index.write_batch():
        # Inside the transaction body, another thread must NOT be able to take
        # the lock (and slip a write into this transaction).
        thread = threading.Thread(target=_try_acquire)
        thread.start()
        thread.join()

    assert other_thread_got_lock == [False]



def test_foreground_search_reads_committed_snapshot_during_batch(tmp_path):
    image_index.set_db_path(tmp_path / "concurrent.db")
    image_index.upsert_image("committed.jpg")
    ready, release, read_done = (threading.Event() for _ in range(3))
    results, failures = [], []

    def write():
        try:
            with image_index.write_batch():
                image_index.upsert_image("uncommitted.jpg")
                ready.set()
                if not release.wait(5):
                    raise TimeoutError("reader did not finish")
                raise ValueError("rollback scanner chunk")
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001 - collect thread failure for assertion
            failures.append(exc)

    def read():
        try:
            results.extend(image_index.search_images())
        except Exception as exc:  # noqa: BLE001 - collect thread failure for assertion
            failures.append(exc)
        finally:
            read_done.set()

    writer = threading.Thread(target=write)
    reader = threading.Thread(target=read)
    writer.start()
    try:
        assert ready.wait(5)
        reader.start()
        assert read_done.wait(1), "search waited for the background write transaction"
        assert results == ["committed.jpg"]
    finally:
        release.set()
        writer.join(5)
        if reader.ident is not None:
            reader.join(5)
        image_index.close()
    assert not writer.is_alive() and not reader.is_alive()
    assert failures == []


@pytest.fixture
def catalog(tmp_path):
    image_index.set_db_path(tmp_path / "catalog.db")
    try:
        yield image_index
    finally:
        image_index.close()


def test_batch_reads_own_changes_and_other_thread_reads_committed_facets(catalog):
    catalog.upsert_image("old.jpg", mtime=1, size=2, phash=0)
    catalog.set_note("old.jpg", "old note")
    catalog.add_image_tag("old.jpg", "trip/old")
    catalog.set_cull_state("old.jpg", "pick")
    catalog.save_smart_album("old", "{}")
    catalog.add_library_root("old-root")
    done = threading.Event()
    results, failures = {}, []

    def read():
        try:
            results.update(
                image=catalog.get_image("new.jpg"), paths=catalog.all_image_paths(),
                count=catalog.count_images(), stored=catalog.stored_paths(),
                note=catalog.get_note("old.jpg"), notes=catalog.paths_with_notes(),
                tags=catalog.tags_of_image("old.jpg"), all_tags=catalog.all_tag_paths(),
                tagged=catalog.images_with_tag("trip"), cull=catalog.get_cull_state("old.jpg"),
                picked=catalog.paths_with_cull_state("pick"),
                filtered=catalog.filter_by_cull(["old.jpg"], "pick"),
                albums=catalog.list_smart_albums(), album=catalog.get_smart_album("new"),
                roots=catalog.list_library_roots(), similar=catalog.similar_by_phash(0),
                fingerprints=list(catalog.iter_image_fingerprints()),
            )
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            failures.append(exc)
        finally:
            done.set()

    reader = threading.Thread(target=read)
    with pytest.raises(ValueError, match="rollback"), catalog.write_batch():
        catalog.upsert_image("new.jpg")
        catalog.set_note("old.jpg", "new note")
        catalog.add_image_tag("old.jpg", "trip/new")
        catalog.set_cull_state("old.jpg", "reject")
        catalog.save_smart_album("new", "{}")
        catalog.add_library_root("new-root")
        assert catalog.get_image("new.jpg") is not None
        assert catalog.get_note("old.jpg") == "new note"
        assert "trip/new" in catalog.tags_of_image("old.jpg")
        reader.start()
        try:
            assert done.wait(2)
            assert failures == []
            assert results["image"] is None and results["count"] == 1
            assert results["paths"] == results["stored"] == ["old.jpg"]
            assert results["note"] == "old note" and results["notes"] == ["old.jpg"]
            assert results["tags"] == ["trip/old"]
            assert results["all_tags"] == ["trip", "trip/old"]
            assert results["tagged"] == results["picked"] == results["filtered"] == ["old.jpg"]
            assert results["cull"] == "pick" and results["album"] is None
            assert [a["name"] for a in results["albums"]] == ["old"]
            assert results["roots"] == ["old-root"]
            assert results["similar"] == [("old.jpg", 0)]
            assert results["fingerprints"] == [("old.jpg", 1.0, 2)]
        finally:
            reader.join(5)
        raise ValueError("rollback")
    assert not reader.is_alive()
    assert catalog.get_note("old.jpg") == "old note"
    assert catalog.get_image("new.jpg") is None


def test_foreground_tag_write_survives_scanner_rollback(catalog):
    ready, release, done = (threading.Event() for _ in range(3))
    failures = []

    def scan():
        try:
            with catalog.write_batch():
                catalog.upsert_image("rolled-back.jpg")
                ready.set()
                if not release.wait(5):
                    raise TimeoutError("release scanner")
                raise ValueError("rollback")
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            failures.append(exc)

    def tag():
        try:
            catalog.add_image_tag("retained.jpg", "trip/retained")
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            failures.append(exc)
        finally:
            done.set()

    writer, tagger = threading.Thread(target=scan), threading.Thread(target=tag)
    writer.start()
    try:
        assert ready.wait(5)
        tagger.start()
        assert not done.wait(.05)
    finally:
        release.set()
        writer.join(5)
        if tagger.ident is not None:
            tagger.join(5)
    assert not writer.is_alive() and not tagger.is_alive() and not failures
    assert catalog.get_image("rolled-back.jpg") is None
    assert catalog.tags_of_image("retained.jpg") == ["trip/retained"]


def test_failed_query_releases_snapshot_and_reader_is_query_only(catalog, monkeypatch):
    import sqlite3
    catalog.upsert_image("before.jpg")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        catalog._reader.execute("DELETE FROM images")
    with monkeypatch.context() as patch:
        def bad_query(_query):
            raise ValueError("invalid query")
        patch.setattr(catalog, "_query_where", bad_query)
        with pytest.raises(ValueError, match="invalid query"):
            catalog.search_images()
    assert not catalog._reader.in_transaction
    catalog.upsert_image("after.jpg")
    assert sorted(catalog.search_images()) == ["after.jpg", "before.jpg"]


def test_close_waits_for_active_reader_and_reopens_without_deadlock(catalog, monkeypatch):
    catalog.upsert_image("persisted.jpg")
    ready, release, closed = (threading.Event() for _ in range(3))
    failures = []
    found = []
    original = catalog._query_where

    def paused(query):
        ready.set()
        if not release.wait(5):
            raise TimeoutError("release reader")
        return original(query)

    def read():
        try:
            found.append(catalog.search_images())
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            failures.append(exc)

    def close():
        try:
            catalog.close()
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            failures.append(exc)
        finally:
            closed.set()

    monkeypatch.setattr(catalog, "_query_where", paused)
    reader, closer = threading.Thread(target=read), threading.Thread(target=close)
    reader.start()
    try:
        assert ready.wait(5)
        closer.start()
        assert not closed.wait(.05)
    finally:
        release.set()
        reader.join(5)
        if closer.ident is not None:
            closer.join(5)
    assert not reader.is_alive() and not closer.is_alive() and not failures
    assert found == [["persisted.jpg"]]
    assert catalog._reader is None and catalog._conn is None
    assert catalog.search_images() == ["persisted.jpg"]


def test_fingerprint_yield_does_not_pin_reader(catalog):
    with catalog.write_batch():
        for number in range(1003):
            catalog.upsert_image(f"{number:04}.jpg", mtime=1, size=2)
    iterator = catalog.iter_image_fingerprints()
    assert next(iterator) == ("0000.jpg", 1.0, 2)
    assert not catalog._reader.in_transaction
    catalog.close()
    assert len(list(iterator)) == 1002



def test_real_scanner_exposes_only_committed_chunk(catalog, tmp_path, monkeypatch):
    from PIL import Image
    from Imervue.library import scanner as scanner_module
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 3), "red").save(source)
    ready, release = threading.Event(), threading.Event()
    original = scanner_module._store
    failures = []

    def paused(row):
        original(row)
        ready.set()
        if not release.wait(5):
            raise TimeoutError("release scanner chunk")

    monkeypatch.setattr(scanner_module, "_store", paused)
    scan = scanner_module.LibraryScanner([str(tmp_path)], with_phash=False)
    scan.error.connect(failures.append)
    thread = threading.Thread(target=scan.run)
    thread.start()
    try:
        assert ready.wait(5)
        assert catalog.search_images() == []
        assert catalog.get_image(str(source)) is None
        assert scan.job_state.snapshot().items[0].status == "pending"
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not failures
    assert catalog.search_images() == [str(source)]
    assert scan.job_state.snapshot().items[0].status == "succeeded"



def test_single_query_uses_sqlite_snapshot_without_extra_begin(catalog):
    catalog.upsert_image("photo.jpg")
    catalog.add_image_tag("photo.jpg", "trip/cat")
    statements = []
    catalog._reader.set_trace_callback(statements.append)
    assert catalog.get_image("photo.jpg") is not None
    assert not any(sql in {"BEGIN", "ROLLBACK"} for sql in statements)
    statements.clear()
    assert catalog.tags_of_image("photo.jpg") == ["trip/cat"]
    assert statements.count("BEGIN") == statements.count("ROLLBACK") == 1
    catalog._reader.set_trace_callback(None)



def test_multi_query_tags_keep_one_snapshot_across_writer_commit(catalog, monkeypatch):
    catalog.add_image_tag("photo.jpg", "trip/old")
    ready, release = threading.Event(), threading.Event()
    results, failures = [], []
    original = catalog.tag_path_of

    def paused(tag_id):
        ready.set()
        if not release.wait(5):
            raise TimeoutError("release tag reader")
        return original(tag_id)

    monkeypatch.setattr(catalog, "tag_path_of", paused)

    def read():
        try:
            results.extend(catalog.tags_of_image("photo.jpg"))
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            failures.append(exc)

    reader = threading.Thread(target=read)
    reader.start()
    try:
        assert ready.wait(5)
        with catalog.write_batch():
            catalog.delete_tag_path("trip/old")
            catalog.add_image_tag("photo.jpg", "trip/new")
    finally:
        release.set()
        reader.join(5)
    assert not reader.is_alive() and not failures
    assert results == ["trip/old"]
    assert catalog.tags_of_image("photo.jpg") == ["trip/new"]
