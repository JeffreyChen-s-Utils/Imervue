"""Tests for Imervue.image.recipe_store."""
from __future__ import annotations

import json

import pytest

from Imervue.image.recipe import Recipe, clear_identity_cache
from Imervue.image.recipe_store import RecipeStore


@pytest.fixture
def store(tmp_path):
    s = RecipeStore(store_path=tmp_path / "recipes.json")
    yield s


@pytest.fixture
def sample_image(tmp_path):
    """Create a real-ish file on disk so file_identity returns a stable hash."""
    p = tmp_path / "sample.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 1000)
    clear_identity_cache()
    return p


# ======================================================================
# Basic get/set/delete
# ======================================================================

class TestStoreBasic:
    def test_empty_store_returns_none(self, store):
        assert store.get("nonexistent") is None
        assert len(store) == 0

    def test_set_and_get_by_identity(self, store):
        r = Recipe(brightness=0.3)
        store.set("abc123", r)
        got = store.get("abc123")
        assert got is not None
        assert got.brightness == pytest.approx(0.3)

    def test_identity_recipe_is_not_stored(self, store):
        store.set("abc123", Recipe())
        assert store.get("abc123") is None
        assert len(store) == 0

    def test_setting_identity_recipe_removes_existing_entry(self, store):
        store.set("abc123", Recipe(brightness=0.3))
        assert len(store) == 1
        store.set("abc123", Recipe())
        assert len(store) == 0

    def test_delete_removes_entry(self, store):
        store.set("abc123", Recipe(brightness=0.3))
        store.delete("abc123")
        assert store.get("abc123") is None

    def test_delete_nonexistent_is_noop(self, store):
        store.delete("nonexistent")  # must not raise
        assert len(store) == 0

    def test_empty_identity_is_rejected(self, store):
        store.set("", Recipe(brightness=0.3))
        assert len(store) == 0
        assert store.get("") is None


# ======================================================================
# Persistence
# ======================================================================

class TestStorePersistence:
    def test_write_creates_file(self, store):
        assert not store.path.exists()
        store.set("abc123", Recipe(brightness=0.3))
        assert store.path.exists()

    def test_file_content_is_valid_json(self, store):
        store.set("abc123", Recipe(brightness=0.3))
        data = json.loads(store.path.read_text(encoding="utf-8"))
        assert "abc123" in data
        assert "recipe" in data["abc123"]
        assert data["abc123"]["recipe"]["brightness"] == 0.3

    def test_survives_reload(self, tmp_path):
        path = tmp_path / "r.json"
        s1 = RecipeStore(store_path=path)
        s1.set("abc123", Recipe(brightness=0.3, contrast=-0.2))

        s2 = RecipeStore(store_path=path)
        got = s2.get("abc123")
        assert got is not None
        assert got.brightness == pytest.approx(0.3)
        assert got.contrast == pytest.approx(-0.2)

    def test_corrupt_file_is_tolerated(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text("not valid json{{{", encoding="utf-8")
        s = RecipeStore(store_path=path)
        assert s.get("anything") is None
        assert len(s) == 0

    def test_non_dict_file_is_tolerated(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        s = RecipeStore(store_path=path)
        assert len(s) == 0

    def test_atomic_write_no_tmp_leftover(self, store):
        store.set("abc", Recipe(brightness=0.1))
        tmp = store.path.with_suffix(store.path.suffix + ".tmp")
        assert not tmp.exists()

    def test_last_path_persisted(self, store):
        store.set("abc123", Recipe(brightness=0.3), last_path="C:/foo/bar.png")
        data = json.loads(store.path.read_text(encoding="utf-8"))
        assert data["abc123"]["last_path"] == "C:/foo/bar.png"


# ======================================================================
# Path-based convenience wrappers
# ======================================================================

class TestStorePathBased:
    def test_set_and_get_for_path(self, store, sample_image):
        store.set_for_path(str(sample_image), Recipe(brightness=0.4))
        got = store.get_for_path(str(sample_image))
        assert got is not None
        assert got.brightness == pytest.approx(0.4)

    def test_missing_file_returns_none(self, store, tmp_path):
        result = store.get_for_path(str(tmp_path / "missing.png"))
        assert result is None

    def test_delete_for_path(self, store, sample_image):
        store.set_for_path(str(sample_image), Recipe(brightness=0.4))
        store.delete_for_path(str(sample_image))
        assert store.get_for_path(str(sample_image)) is None

    def test_identity_follows_content_not_path(self, store, tmp_path):
        """Recipe follows the file bytes, not the filename."""
        src = tmp_path / "src.png"
        src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"content-a" * 100)
        clear_identity_cache()

        store.set_for_path(str(src), Recipe(brightness=0.5))

        # Rename — identity is stable because content is unchanged
        dst = tmp_path / "renamed.png"
        src.rename(dst)
        clear_identity_cache()

        got = store.get_for_path(str(dst))
        assert got is not None
        assert got.brightness == pytest.approx(0.5)

    def test_identity_invalidates_on_content_change(self, store, sample_image):
        store.set_for_path(str(sample_image), Recipe(brightness=0.5))

        # Write different content
        sample_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"different" * 200)
        clear_identity_cache()

        # Old recipe no longer matches (stored under different identity)
        assert store.get_for_path(str(sample_image)) is None


# ======================================================================
# Unknown field handling
# ======================================================================

class TestStoreUnknownFields:
    def test_unknown_recipe_field_survives_reload(self, tmp_path):
        path = tmp_path / "r.json"
        s1 = RecipeStore(store_path=path)
        r = Recipe(brightness=0.3, extra={"panel_v": 5})
        s1.set("abc", r)

        s2 = RecipeStore(store_path=path)
        got = s2.get("abc")
        assert got is not None
        assert got.extra.get("panel_v") == 5

    def test_entries_without_recipe_key_are_dropped(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({
            "abc": {"last_path": "/foo"},  # missing recipe key
            "def": {"recipe": {"brightness": 0.2}},
        }), encoding="utf-8")
        s = RecipeStore(store_path=path)
        assert s.get("abc") is None
        assert s.get("def") is not None
