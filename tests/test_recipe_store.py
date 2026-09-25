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
        assert data["abc123"]["recipe"]["brightness"] == pytest.approx(0.3)

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


# ======================================================================
# Malformed stored recipes — known decode errors are dropped, bugs propagate
# ======================================================================

_BAD_RECIPES = [
    {"crop": ["a", 0, 1, 1]},                     # ValueError: int("a")
    {"tone_curve_rgb": [[0.5]]},                  # IndexError: short curve point
    {"extra": 5},                                 # TypeError: non-mapping extra
]


def _write_store(path, entries):
    path.write_text(json.dumps(entries), encoding="utf-8")


@pytest.mark.parametrize("bad", _BAD_RECIPES)
def test_undecodable_entry_is_dropped_on_load(tmp_path, bad):
    path = tmp_path / "recipes.json"
    _write_store(path, {"id1": {"recipe": bad, "last_path": ""}})
    assert RecipeStore(store_path=path).get("id1") is None


@pytest.mark.parametrize("bad", _BAD_RECIPES)
def test_an_undecodable_entry_is_written_back_as_it_was(tmp_path, bad):
    """Saving another photo's recipe used to drop it from the file for good."""
    path = tmp_path / "recipes.json"
    _write_store(path, {"id1": {"recipe": bad, "last_path": "/a.jpg"}})
    store = RecipeStore(store_path=path)
    store.set("id2", Recipe(exposure=0.5))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["id1"] == {"recipe": bad, "last_path": "/a.jpg"}
    assert saved["id2"]["recipe"]["exposure"] == pytest.approx(0.5)


def test_a_new_recipe_replaces_an_undecodable_one(tmp_path):
    path = tmp_path / "recipes.json"
    _write_store(path, {"id1": {"recipe": _BAD_RECIPES[0]}})
    store = RecipeStore(store_path=path)
    store.set("id1", Recipe(exposure=0.25))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["id1"]["recipe"]["exposure"] == pytest.approx(0.25)


class TestUnreadableStoreFile:
    """A recipes.json that could not be read was replaced by the next save."""

    @staticmethod
    def _copies(path):
        return sorted(path.parent.glob(f"{path.name}.unreadable-*"))

    @pytest.mark.parametrize("content", [b"not valid json{{{", b"[1, 2, 3]", b"\xff\xfe{}"])
    def test_a_copy_is_kept_before_the_first_save(self, tmp_path, content):
        path = tmp_path / "recipes.json"
        path.write_bytes(content)
        store = RecipeStore(store_path=path)
        store.set("id1", Recipe(exposure=0.5))
        (copy,) = self._copies(path)
        assert copy.read_bytes() == content
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["id1"]["recipe"]["exposure"] == pytest.approx(0.5)

    def test_a_readable_store_keeps_no_copy(self, store):
        store.set("id1", Recipe(exposure=0.5))
        RecipeStore(store_path=store.path).set("id2", Recipe(exposure=0.1))
        assert self._copies(store.path) == []

    def test_the_file_is_left_alone_while_no_copy_can_be_made(self, tmp_path, monkeypatch):
        import shutil
        path = tmp_path / "recipes.json"
        path.write_text("not valid json{{{", encoding="utf-8")

        def refuse(*_args, **_kwargs):
            raise PermissionError("disk full")

        monkeypatch.setattr(shutil, "copy2", refuse)
        RecipeStore(store_path=path).set("id1", Recipe(exposure=0.5))
        assert path.read_text(encoding="utf-8") == "not valid json{{{"

    def test_reset_forgets_the_failed_read(self, tmp_path):
        path = tmp_path / "recipes.json"
        path.write_text("not valid json{{{", encoding="utf-8")
        store = RecipeStore(store_path=path)
        assert len(store) == 0
        path.write_text("{}", encoding="utf-8")
        store._reset_for_tests()  # noqa: SLF001
        store.set("id1", Recipe(exposure=0.5))
        assert self._copies(path) == []


@pytest.mark.parametrize("bad", _BAD_RECIPES)
def test_undecodable_variant_returns_none(store, bad):
    store.save_variant("id1", "v", Recipe(exposure=0.5))
    store._entries["id1"]["variants"]["v"] = bad  # noqa: SLF001 - corrupt it in place
    assert store.get_variant("id1", "v") is None


def test_unexpected_decode_error_is_not_swallowed(store, monkeypatch):
    store.set("id1", Recipe(exposure=0.5))

    def boom(_data):
        raise RuntimeError("bug")

    monkeypatch.setattr(Recipe, "from_dict", staticmethod(boom))
    with pytest.raises(RuntimeError):
        store.get("id1")


class TestRekey:
    def test_the_recipe_and_its_variants_move(self, store):
        store.set("old", Recipe(exposure=1.0), last_path="a.jpg")
        store.save_variant("old", "bw", Recipe(saturation=-1.0))
        assert store.rekey("old", "new") is True
        assert store.get("old") is None
        assert store.get("new").exposure == pytest.approx(1.0)
        assert store.get_variant("new", "bw").saturation == pytest.approx(-1.0)

    def test_a_transform_applies_to_every_recipe(self, store):
        store.set("old", Recipe(exposure=1.0))
        store.save_variant("old", "v", Recipe(exposure=0.5))
        store.rekey("old", "new", lambda r: Recipe(exposure=r.exposure * 2))
        assert store.get("new").exposure == pytest.approx(2.0)
        assert store.get_variant("new", "v").exposure == pytest.approx(1.0)

    def test_nothing_moves_when_one_recipe_cannot_follow(self, store):
        store.set("old", Recipe(exposure=1.0))
        store.save_variant("old", "masked", Recipe(exposure=0.5))
        assert store.rekey("old", "new", lambda r: None if r.exposure < 1 else r) is False
        assert store.get("old").exposure == pytest.approx(1.0) and store.get("new") is None

    @pytest.mark.parametrize(("old", "new"), [("", "new"), ("old", ""), ("old", "old"), ("gone", "new")])
    def test_nothing_to_move(self, store, old, new):
        store.set("old", Recipe(exposure=1.0))
        assert store.rekey(old, new) is False
        assert store.get("old") is not None

    def test_the_move_is_saved(self, store, tmp_path):
        store.set("old", Recipe(exposure=1.0))
        store.rekey("old", "new")
        reloaded = RecipeStore(store._path)  # noqa: SLF001
        assert reloaded.get("new").exposure == pytest.approx(1.0)


class TestCarryRecipe:
    """An EXIF rewrite or a lossless turn changed the identity and orphaned the edits."""

    @pytest.fixture
    def jpeg(self, tmp_path):
        from PIL import Image
        path = tmp_path / "p.jpg"
        Image.new("RGB", (60, 40), (10, 120, 200)).save(path, quality=95)
        clear_identity_cache()
        return str(path)

    def test_a_gps_write_keeps_the_recipe(self, jpeg):
        from Imervue.image.gps_geotag import write_gps
        from Imervue.image.recipe_store import recipe_store
        recipe_store.set_for_path(jpeg, Recipe(exposure=0.8, crop=(1, 2, 30, 20)))
        assert write_gps(jpeg, 25.03, 121.56)
        kept = recipe_store.get_for_path(jpeg)
        assert kept is not None and kept.crop == (1, 2, 30, 20)

    def test_a_lossless_turn_turns_the_recipe(self, jpeg):
        from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
        from Imervue.image.recipe_store import recipe_store
        recipe_store.set_for_path(jpeg, Recipe(exposure=0.8, crop=(0, 0, 30, 20)))
        assert lossless_rotate(jpeg, clockwise=True)
        turned = recipe_store.get_for_path(jpeg)
        assert turned is not None and turned.exposure == pytest.approx(0.8)
        assert turned.crop == (20, 0, 20, 30)           # the top-left box, now top-right

    def test_a_recipe_with_masks_stays_under_the_old_identity(self, jpeg):
        from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
        from Imervue.image.recipe import file_identity
        from Imervue.image.recipe_store import recipe_store
        recipe = Recipe(exposure=0.8)
        recipe.extra["masks"] = [{"type": "radial", "params": {"cx": 5}}]
        recipe_store.set_for_path(jpeg, recipe)
        before = file_identity(jpeg)
        lossless_rotate(jpeg, clockwise=True)
        assert recipe_store.get(before) is not None       # turning back finds it again
        assert recipe_store.get_for_path(jpeg) is None

    def test_a_change_that_did_nothing_moves_nothing(self, jpeg):
        from Imervue.image.recipe_store import carry_recipe, recipe_store
        recipe_store.set_for_path(jpeg, Recipe(exposure=0.8))
        assert carry_recipe(jpeg, lambda: False) is False
        assert recipe_store.get_for_path(jpeg) is not None


def test_a_store_file_with_a_bom_is_read(tmp_path):
    path = tmp_path / "recipes.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        {"id1": {"recipe": {"exposure": 0.5}}}).encode("utf-8"))
    store = RecipeStore(store_path=path)
    assert store.get("id1").exposure == pytest.approx(0.5)
    store.set("id2", Recipe(exposure=0.1))
    assert sorted(tmp_path.glob("recipes.json.unreadable-*")) == []
