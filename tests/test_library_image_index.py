"""
Unit tests for ``Imervue.library.image_index``.
"""
from __future__ import annotations

import pytest

from Imervue.library import image_index


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    """Point the library index at a per-test DB so nothing leaks."""
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


class TestImagesCRUD:
    def test_upsert_and_get(self, tmp_path):
        p = str(tmp_path / "a.png")
        image_index.upsert_image(p, width=800, height=600, size=12345)
        row = image_index.get_image(p)
        assert row is not None
        assert row["width"] == 800
        assert row["height"] == 600
        assert row["ext"] == "png"

    def test_upsert_preserves_fields_on_partial_update(self, tmp_path):
        p = str(tmp_path / "b.jpg")
        image_index.upsert_image(p, width=200, height=100)
        image_index.upsert_image(p, phash=42)
        row = image_index.get_image(p)
        assert row["width"] == 200
        assert row["height"] == 100
        assert row["phash"] == 42

    def test_delete_cascades(self, tmp_path):
        p = str(tmp_path / "c.png")
        image_index.upsert_image(p)
        image_index.set_note(p, "note")
        image_index.set_cull_state(p, "pick")
        image_index.add_image_tag(p, "animal/cat")
        image_index.delete_image(p)
        assert image_index.get_image(p) is None
        assert image_index.get_note(p) == ""
        assert image_index.get_cull_state(p) == "unflagged"
        assert image_index.tags_of_image(p) == []

    def test_search_by_ext_and_name(self, tmp_path):
        for name in ("cat.png", "dog.png", "cat.jpg"):
            image_index.upsert_image(str(tmp_path / name))
        hits = image_index.search_images(exts=["png"])
        assert sorted(hits) == sorted([
            str(tmp_path / "cat.png"), str(tmp_path / "dog.png"),
        ])
        name_hits = image_index.search_images(name_contains="cat")
        assert sorted(name_hits) == sorted([
            str(tmp_path / "cat.png"), str(tmp_path / "cat.jpg"),
        ])


class TestNotes:
    def test_set_and_get(self, tmp_path):
        p = str(tmp_path / "a.png")
        image_index.set_note(p, "hello")
        assert image_index.get_note(p) == "hello"

    def test_empty_note_clears_row(self, tmp_path):
        p = str(tmp_path / "a.png")
        image_index.set_note(p, "x")
        image_index.set_note(p, "")
        assert image_index.get_note(p) == ""
        assert p not in image_index.paths_with_notes()


class TestHierarchicalTags:
    def test_create_and_lookup(self, tmp_path):
        tid = image_index.create_tag_path("animal/cat/british")
        assert isinstance(tid, int)
        assert "animal/cat/british" in image_index.all_tag_paths()
        assert image_index.tag_path_of(tid) == "animal/cat/british"

    def test_images_with_tag_includes_descendants(self, tmp_path):
        img = str(tmp_path / "x.png")
        image_index.add_image_tag(img, "animal/cat/british")
        assert img in image_index.images_with_tag("animal")
        assert img in image_index.images_with_tag("animal/cat")

    def test_remove_tag(self, tmp_path):
        img = str(tmp_path / "x.png")
        image_index.add_image_tag(img, "a/b")
        assert image_index.remove_image_tag(img, "a/b")
        assert img not in image_index.images_with_tag("a/b")

    def test_delete_tag_removes_descendants(self):
        image_index.create_tag_path("animal/cat/british")
        image_index.create_tag_path("animal/dog")
        assert image_index.delete_tag_path("animal")
        assert image_index.all_tag_paths() == []

    def test_create_tag_rejects_empty(self):
        with pytest.raises(ValueError):
            image_index.create_tag_path("   /  ")


class TestCulling:
    def test_state_round_trip(self, tmp_path):
        p = str(tmp_path / "x.png")
        image_index.set_cull_state(p, "pick")
        assert image_index.get_cull_state(p) == "pick"
        image_index.set_cull_state(p, "unflagged")
        assert image_index.get_cull_state(p) == "unflagged"

    def test_invalid_state_raises(self, tmp_path):
        with pytest.raises(ValueError):
            image_index.set_cull_state(str(tmp_path / "x.png"), "bogus")

    def test_filter_by_cull(self, tmp_path):
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        c = str(tmp_path / "c.png")
        image_index.set_cull_state(a, "pick")
        image_index.set_cull_state(b, "reject")
        assert image_index.filter_by_cull([a, b, c], "pick") == [a]
        assert image_index.filter_by_cull([a, b, c], "reject") == [b]
        assert image_index.filter_by_cull([a, b, c], "unflagged") == [c]
        assert image_index.filter_by_cull([a, b, c], None) == [a, b, c]


class TestSmartAlbumsPersistence:
    def test_save_list_delete(self):
        image_index.save_smart_album("A", '{"min_width": 100}')
        image_index.save_smart_album("B", '{"cull": "pick"}')
        names = [r["name"] for r in image_index.list_smart_albums()]
        assert names == ["A", "B"]
        assert image_index.delete_smart_album("A")
        assert image_index.get_smart_album("A") is None


class TestPhashQuery:
    def test_similar_by_phash_distance_threshold(self, tmp_path):
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        c = str(tmp_path / "c.png")
        image_index.upsert_image(a, phash=0)
        image_index.upsert_image(b, phash=0b11)        # distance 2
        image_index.upsert_image(c, phash=0xFFFFFFFF)  # very far

        results = image_index.similar_by_phash(0, max_distance=3)
        paths = [p for p, _ in results]
        assert a in paths
        assert b in paths
        assert c not in paths


class TestLibraryRoots:
    def test_add_remove_list(self, tmp_path):
        image_index.add_library_root(str(tmp_path))
        image_index.add_library_root(str(tmp_path))  # idempotent
        assert image_index.list_library_roots() == [str(tmp_path)]
        assert image_index.remove_library_root(str(tmp_path))
        assert image_index.list_library_roots() == []
