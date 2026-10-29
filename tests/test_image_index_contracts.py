"""Catalog persistence contracts across domain and connection boundaries."""
import sqlite3

import pytest

from Imervue.library import image_index as index


@pytest.mark.parametrize("text", ["", "/", " / / ", "  "])
def test_empty_tag_paths_keep_distinct_public_results(text):
    with pytest.raises(ValueError, match="empty tag path"):
        index.create_tag_path(text)
    assert index.delete_tag_path(text) is False
    assert index.remove_image_tag("a.jpg", text) is False
    assert index.images_with_tag(text) == []


@pytest.mark.parametrize("text", ["animal/cat", " animal / cat /", "//animal//cat//"])
def test_tag_path_normalization_and_descendant_links(text):
    index.add_image_tag("b.jpg", text)
    index.add_image_tag("a.jpg", "animal/cat/kitten")
    assert index.tags_of_image("b.jpg") == ["animal/cat"]
    assert index.images_with_tag(text) == ["a.jpg", "b.jpg"]
    assert index.images_with_tag(text, include_descendants=False) == ["b.jpg"]
    assert index.remove_image_tag("b.jpg", text)
    assert not index.remove_image_tag("b.jpg", text)
    assert index.delete_tag_path(text)
    assert index.tags_of_image("a.jpg") == []
    assert index.all_tag_paths() == ["animal"]


def test_batch_rollback_covers_every_domain():
    with pytest.raises(RuntimeError, match="abort"), index.write_batch():
        index.upsert_image("a.jpg", phash=(1 << 64) - 1)
        index.set_note("a.jpg", "note")
        index.add_image_tag("a.jpg", "one/two")
        index.set_cull_state("a.jpg", index.CULL_PICK)
        index.save_smart_album("album", "opaque")
        index.add_library_root("root")
        assert index.get_note("a.jpg") == "note"
        assert index.images_with_tag("one") == ["a.jpg"]
        raise RuntimeError("abort")
    assert index.all_image_paths() == []
    assert index.paths_with_notes() == []
    assert index.all_tag_paths() == []
    assert index.paths_with_cull_state(index.CULL_PICK) == []
    assert index.list_smart_albums() == []
    assert index.list_library_roots() == []


def test_unknown_fields_survive_upsert_but_decoded_none_clears():
    index.upsert_image("a.jpg", width=10, height=20, phash=(1 << 64) - 1)
    index.upsert_image("a.jpg", width=None, height=None, phash=None)
    row = index.get_image("a.jpg")
    assert (row["width"], row["height"], row["phash"]) == (10, 20, -1)
    assert index.similar_by_phash((1 << 64) - 1) == [("a.jpg", 0)]
    index.set_decoded_fields("a.jpg", width=None, height=None, phash=None)
    row = index.get_image("a.jpg")
    assert (row["width"], row["height"], row["phash"]) == (None, None, None)


def test_relocation_preserves_table_specific_existing_rows():
    index.upsert_image("a.jpg", width=10)
    index.set_note("a.jpg", "source")
    index.set_note("b.jpg", "destination")
    index.set_cull_state("a.jpg", index.CULL_PICK)
    index.move_paths({"a.jpg": "b.jpg"}, keep_existing=True)
    assert index.get_image("a.jpg") is None
    assert index.get_image("b.jpg")["width"] == 10
    assert index.get_note("a.jpg") == "source"
    assert index.get_note("b.jpg") == "destination"
    assert index.get_cull_state("b.jpg") == index.CULL_PICK


def test_path_switch_reopens_one_canonical_catalog(tmp_path):
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    index.set_db_path(first)
    writer = index.conn()
    index.upsert_image("first.jpg")
    assert index.count_images() == 1
    index.set_db_path(second)
    with pytest.raises(sqlite3.ProgrammingError):
        writer.execute("SELECT 1")
    assert index.count_images() == 0
    index.upsert_image("second.jpg")
    index.set_db_path(first)
    assert index.all_image_paths() == ["first.jpg"]


def test_fingerprints_release_snapshot_after_full_page():
    with index.write_batch():
        for number in range(1001):
            index.upsert_image(f"{number:04}.jpg", size=number, mtime=number)
    iterator = index.iter_image_fingerprints()
    first = [next(iterator) for _ in range(1000)]
    assert first[0] == ("0000.jpg", 0.0, 0)
    assert first[-1] == ("0999.jpg", 999.0, 999)
    index.close()
    assert list(iterator) == [("1000.jpg", 1000.0, 1000)]


def test_reader_open_failure_closes_unpublished_writer(monkeypatch):
    owner = index.conn.__globals__
    connect = sqlite3.connect
    writers = []

    def track_connection(*args, **kwargs):
        connection = connect(*args, **kwargs)
        writers.append(connection)
        return connection

    def fail_reader(_path):
        raise sqlite3.OperationalError("reader failed")

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", track_connection)
        patch.setitem(owner, "_open_reader", fail_reader)
        with pytest.raises(sqlite3.OperationalError, match="reader failed"):
            index.conn()
    assert len(writers) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        writers[0].execute("SELECT 1")
    assert index.count_images() == 0


def test_reader_configuration_failure_closes_reader(monkeypatch, tmp_path):
    calls = []

    class Reader:
        def execute(self, sql):
            calls.append(sql)
            raise sqlite3.OperationalError("configure failed")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: Reader())
    with pytest.raises(sqlite3.OperationalError, match="configure failed"):
        index._open_reader(tmp_path / "reader.db")
    assert calls == ["PRAGMA query_only = ON", "close"]
