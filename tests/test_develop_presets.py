"""Tests for the develop-preset store and batch recipe sync."""
from __future__ import annotations

import pytest

from Imervue.image.develop_presets import (
    PRESETS_KEY,
    DevelopPresetStore,
    apply_recipe_to_paths,
)
from Imervue.image.recipe import Recipe


class _FakeStore:
    """Records set_for_path calls in place of the real recipe store."""

    def __init__(self):
        self.calls: list[tuple[str, Recipe]] = []

    def set_for_path(self, path, recipe):
        self.calls.append((path, recipe))


class TestDevelopPresetStore:
    def test_save_and_get_round_trip(self):
        store = DevelopPresetStore({})
        assert store.save("Warm", Recipe(exposure=1.5)) is True
        assert store.get("Warm").exposure == pytest.approx(1.5)

    def test_names_are_sorted(self):
        store = DevelopPresetStore({})
        store.save("Zebra", Recipe())
        store.save("Alpha", Recipe())
        assert store.names() == ["Alpha", "Zebra"]

    def test_empty_name_is_rejected(self):
        settings: dict = {}
        store = DevelopPresetStore(settings)
        assert store.save("  ", Recipe()) is False
        assert store.names() == []

    def test_save_overwrites_existing_name(self):
        store = DevelopPresetStore({})
        store.save("p", Recipe(exposure=0.5))
        store.save("p", Recipe(exposure=-0.5))
        assert store.get("p").exposure == -0.5
        assert store.names() == ["p"]

    def test_get_missing_returns_none(self):
        assert DevelopPresetStore({}).get("nope") is None

    def test_delete(self):
        store = DevelopPresetStore({})
        store.save("p", Recipe())
        assert store.delete("p") is True
        assert store.delete("p") is False

    @pytest.mark.parametrize("old,new,ok", [
        ("p", "q", True),
        ("p", "", False),
        ("p", "p", False),
        ("missing", "q", False),
    ])
    def test_rename_rules(self, old, new, ok):
        store = DevelopPresetStore({})
        store.save("p", Recipe(exposure=0.3))
        store.save("taken", Recipe())
        assert store.rename(old, new) is ok

    def test_rename_into_existing_name_is_rejected(self):
        store = DevelopPresetStore({})
        store.save("p", Recipe())
        store.save("q", Recipe())
        assert store.rename("p", "q") is False

    def test_corrupt_table_is_replaced(self):
        settings = {PRESETS_KEY: "not-a-dict"}
        store = DevelopPresetStore(settings)
        assert store.names() == []
        store.save("p", Recipe())
        assert isinstance(settings[PRESETS_KEY], dict)

    def test_corrupt_entry_get_returns_none(self):
        settings = {PRESETS_KEY: {"p": "garbage"}}
        assert DevelopPresetStore(settings).get("p") is None


class TestApplyRecipeToPaths:
    def test_writes_to_every_path_and_counts(self):
        store = _FakeStore()
        n = apply_recipe_to_paths(Recipe(exposure=1.0), ["a", "b", "c"], store)
        assert n == 3
        assert [p for p, _ in store.calls] == ["a", "b", "c"]

    def test_each_path_gets_an_independent_clone(self):
        store = _FakeStore()
        apply_recipe_to_paths(Recipe(exposure=1.0), ["a", "b"], store)
        first, second = store.calls[0][1], store.calls[1][1]
        assert first is not second
        assert first.exposure == pytest.approx(1.0) and second.exposure == pytest.approx(1.0)

    def test_empty_paths_applies_nothing(self):
        store = _FakeStore()
        assert apply_recipe_to_paths(Recipe(), [], store) == 0
        assert store.calls == []
