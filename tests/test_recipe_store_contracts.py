"""Contracts of ``Imervue.image.recipe_store`` that the split into mixins must keep.

Pins the exact bytes a save writes, the load-time filtering of entries and
variants, the variant edge cases, the identity-recipe rule in ``set``, the
write-failure handling, and the public names other modules import from here.
"""
from __future__ import annotations

import json
import logging
import os

import pytest

from Imervue.image import recipe_store as module
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import RecipeStore

_LOGGER_NAME = "Imervue.recipe_store"


@pytest.fixture
def store(tmp_path):
    return RecipeStore(store_path=tmp_path / "recipes.json")


def _on_disk(store):
    return json.loads(store.path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


# ----------------------------------------------------------------------
# Public surface
# ----------------------------------------------------------------------

def test_the_public_names_stay_importable_from_the_module():
    for name in ("RecipeStore", "recipe_store", "carry_recipe", "logger"):
        assert hasattr(module, name)
    assert isinstance(module.recipe_store, RecipeStore)
    assert module.logger.name == _LOGGER_NAME


def test_the_default_path_ends_in_the_store_filename():
    path = module._default_store_path()  # noqa: SLF001 - pinning the private default
    assert path.name == "recipes.json"
    assert path.parent.name == "recipes"


def test_path_property_reports_the_constructor_path(tmp_path):
    assert RecipeStore(store_path=str(tmp_path / "x.json")).path == tmp_path / "x.json"


# ----------------------------------------------------------------------
# Persisted bytes
# ----------------------------------------------------------------------

def test_saved_bytes_are_sorted_indented_and_keep_non_ascii(store):
    store.set("b-id", Recipe(exposure=0.5), last_path="/照片/b.jpg")
    store.set("a-id", Recipe(exposure=0.25), last_path="/a.jpg")
    text = store.path.read_text(encoding="utf-8")
    expected = json.dumps(_on_disk(store), ensure_ascii=False, indent=2, sort_keys=True)
    assert text == expected
    assert "照片" in text
    assert text.index('"a-id"') < text.index('"b-id"')


def test_an_entry_holds_recipe_last_path_and_variants(store):
    store.set("id1", Recipe(exposure=0.5), last_path="/a.jpg")
    entry = _on_disk(store)["id1"]
    assert set(entry) == {"recipe", "last_path", "variants"}
    assert entry["recipe"] == Recipe(exposure=0.5).normalized().to_dict()
    assert entry["last_path"] == "/a.jpg"
    assert entry["variants"] == {}


def test_reload_round_trips_every_entry(tmp_path, store):
    store.set("id1", Recipe(exposure=0.5), last_path="/a.jpg")
    store.save_variant("id1", "warm", Recipe(temperature=0.2))
    again = RecipeStore(store_path=store.path)
    assert again.get("id1") == Recipe(exposure=0.5).normalized()
    assert again.get_variant("id1", "warm") == Recipe(temperature=0.2).normalized()
    assert again._entries == store._entries  # noqa: SLF001 - same in-memory index


# ----------------------------------------------------------------------
# Load-time filtering
# ----------------------------------------------------------------------

def test_a_missing_store_file_loads_empty_without_a_copy(store):
    assert len(store) == 0
    assert not store.path.exists()


def test_non_dict_variants_and_entries_are_filtered(tmp_path):
    path = tmp_path / "recipes.json"
    good = Recipe(exposure=0.3).to_dict()
    _write(path, {
        "keep": {"recipe": good, "variants": {"ok": good, "bad": 5, 7: good}},
        "listvar": {"recipe": good, "variants": [good]},
        "notdict": "junk",
        "norecipe": {"recipe": [1]},
    })
    store = RecipeStore(store_path=path)
    assert store.list_variants("keep") == ["7", "ok"]
    assert store.list_variants("listvar") == []
    assert store._entries["keep"]["last_path"] == ""  # noqa: SLF001
    assert set(store._undecodable) == {"notdict", "norecipe"}  # noqa: SLF001
    assert len(store) == 2


def test_a_variant_whose_decode_raises_anything_is_dropped(tmp_path, monkeypatch):
    path = tmp_path / "recipes.json"
    good = Recipe(exposure=0.3).to_dict()
    poison = {**good, "_poison": True}
    _write(path, {"id1": {"recipe": good, "variants": {"ok": good, "boom": poison}}})
    real = Recipe.from_dict

    def picky(data):
        if data.get("_poison"):
            raise RuntimeError("bug")
        return real(data)

    monkeypatch.setattr(Recipe, "from_dict", staticmethod(picky))
    assert RecipeStore(store_path=path).list_variants("id1") == ["ok"]


def test_a_read_failure_logs_on_the_store_logger(tmp_path, caplog):
    path = tmp_path / "recipes.json"
    path.write_text("{{{", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        assert len(RecipeStore(store_path=path)) == 0
    assert any("Recipe store read failed" in r.getMessage() for r in caplog.records)


def test_loading_happens_once(store, monkeypatch):
    store.set("id1", Recipe(exposure=0.5))
    calls = []
    monkeypatch.setattr(store, "_load_locked", lambda: calls.append(1))
    store.get("id1")
    len(store)
    assert calls == []


# ----------------------------------------------------------------------
# set / delete
# ----------------------------------------------------------------------

def test_an_identity_recipe_keeps_saved_variants_under_a_reset_master(store):
    store.set("id1", Recipe(exposure=0.5), last_path="/old.jpg")
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    store.set("id1", Recipe(), last_path="/new.jpg")
    entry = _on_disk(store)["id1"]
    assert entry["recipe"] == Recipe().to_dict()
    assert entry["last_path"] == "/new.jpg"
    assert list(entry["variants"]) == ["v"]


def test_an_identity_recipe_for_an_unknown_entry_writes_nothing(store):
    store.set("id1", Recipe())
    assert not store.path.exists()


def test_a_new_master_keeps_the_saved_variants(store):
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    store.set("id1", Recipe(exposure=0.9), last_path="/p.jpg")
    assert store.list_variants("id1") == ["v"]
    assert store.get("id1").exposure == pytest.approx(0.9)


def test_delete_of_an_unknown_identity_writes_nothing(store):
    store.delete("missing")
    assert not store.path.exists()


# ----------------------------------------------------------------------
# Variants
# ----------------------------------------------------------------------

def test_save_variant_strips_the_name_and_seeds_an_identity_master(store):
    store.save_variant("id1", "  warm  ", Recipe(exposure=0.4), last_path="/a.jpg")
    entry = _on_disk(store)["id1"]
    assert list(entry["variants"]) == ["warm"]
    assert entry["recipe"] == Recipe().to_dict()
    assert entry["last_path"] == "/a.jpg"


def test_save_variant_without_last_path_keeps_the_old_one(store):
    store.set("id1", Recipe(exposure=0.5), last_path="/a.jpg")
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    assert _on_disk(store)["id1"]["last_path"] == "/a.jpg"


@pytest.mark.parametrize(("identity", "name"), [("", "v"), ("id1", ""), ("id1", "   ")])
def test_save_variant_ignores_blank_arguments(store, identity, name):
    store.save_variant(identity, name, Recipe(exposure=0.1))
    assert not store.path.exists()


@pytest.mark.parametrize(("identity", "name"), [("", "v"), ("id1", ""), ("nope", "v")])
def test_get_variant_misses_return_none(store, identity, name):
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    assert store.get_variant(identity, name) is None


def test_get_variant_of_a_missing_name_returns_none(store):
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    assert store.get_variant("id1", "other") is None


def test_list_variants_of_blank_or_unknown_identity_is_empty(store):
    assert store.list_variants("") == []
    assert store.list_variants("nope") == []


def test_delete_variant_of_an_unknown_name_leaves_the_file(store):
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    before = store.path.read_bytes()
    os.utime(store.path, (1, 1))
    store.delete_variant("id1", "other")
    store.delete_variant("nope", "v")
    store.delete_variant("", "v")
    store.delete_variant("id1", "")
    assert store.path.read_bytes() == before
    assert store.path.stat().st_mtime == pytest.approx(1)


@pytest.mark.parametrize(("identity", "old", "new"), [
    ("", "v", "w"), ("id1", "", "w"), ("id1", "v", ""), ("id1", "v", "  "),
    ("id1", "v", "v"), ("id1", "v", " v "), ("nope", "v", "w"), ("id1", "missing", "w"),
    ("id1", "v", "taken"),
])
def test_rename_variant_refusals_return_false(store, identity, old, new):
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    store.save_variant("id1", "taken", Recipe(exposure=0.2))
    assert store.rename_variant(identity, old, new) is False
    assert store.list_variants("id1") == ["taken", "v"]


def test_rename_variant_strips_the_new_name(store):
    store.save_variant("id1", "v", Recipe(exposure=0.1))
    assert store.rename_variant("id1", "v", "  w  ") is True
    assert _on_disk(store)["id1"]["variants"].keys() == {"w"}


# ----------------------------------------------------------------------
# Rekey
# ----------------------------------------------------------------------

def test_rekey_passes_non_dict_variants_through(store):
    store.set("old", Recipe(exposure=0.5))
    store._entries["old"]["variants"]["odd"] = 5  # noqa: SLF001 - an entry from a newer build
    seen = []

    def keep(recipe):
        seen.append(recipe)
        return recipe

    assert store.rekey("old", "new", keep) is True
    assert store._entries["new"]["variants"]["odd"] == 5  # noqa: SLF001
    assert len(seen) == 1


def test_rekey_drops_nothing_when_a_variant_fails_to_decode(store):
    store.set("old", Recipe(exposure=0.5))
    store._entries["old"]["variants"]["bad"] = {"extra": 5}  # noqa: SLF001
    assert store.rekey("old", "new", lambda r: r) is False
    assert store.get("old") is not None
    assert store.get("new") is None


def test_rekey_without_transform_moves_the_entry_object(store):
    store.set("old", Recipe(exposure=0.5))
    entry = store._entries["old"]  # noqa: SLF001
    assert store.rekey("old", "new") is True
    assert store._entries["new"] is entry  # noqa: SLF001


# ----------------------------------------------------------------------
# Path wrappers on a missing file
# ----------------------------------------------------------------------

def test_path_wrappers_on_a_missing_file_do_nothing(store, tmp_path):
    missing = str(tmp_path / "gone.png")
    store.set_for_path(missing, Recipe(exposure=0.5))
    store.save_variant_for_path(missing, "v", Recipe(exposure=0.5))
    store.delete_for_path(missing)
    store.delete_variant_for_path(missing, "v")
    assert store.get_for_path(missing) is None
    assert store.list_variants_for_path(missing) == []
    assert store.get_variant_for_path(missing, "v") is None
    assert store.rename_variant_for_path(missing, "v", "w") is False
    assert store.identity_for(missing) == ""
    assert not store.path.exists()


# ----------------------------------------------------------------------
# Write failures
# ----------------------------------------------------------------------

def test_a_failed_write_removes_the_tmp_file_and_keeps_memory(store, monkeypatch, caplog):
    def refuse(*_args):
        raise OSError("locked")

    monkeypatch.setattr(module.os, "replace", refuse)
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        store.set("id1", Recipe(exposure=0.5))
    assert not store.path.exists()
    assert not store.path.with_suffix(".json.tmp").exists()
    assert store.get("id1") is not None
    assert any("Recipe store write failed" in r.getMessage() for r in caplog.records)


def test_an_uncreatable_directory_is_logged_and_skipped(tmp_path, caplog):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    store = RecipeStore(store_path=blocker / "sub" / "recipes.json")
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        store.set("id1", Recipe(exposure=0.5))
    assert any("Cannot create recipe store dir" in r.getMessage() for r in caplog.records)
    assert store.get("id1") is not None


def test_reset_for_tests_rereads_from_disk(store):
    store.set("id1", Recipe(exposure=0.5))
    _write(store.path, {})
    assert len(store) == 1
    store._reset_for_tests()  # noqa: SLF001
    assert len(store) == 0
