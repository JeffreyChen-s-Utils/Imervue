"""Tests for tag / album integrity helpers."""
from __future__ import annotations

import pytest

from Imervue.user_settings.tag_validator import (
    find_duplicate_names,
    find_empty_collections,
    find_name_collisions,
    find_orphaned_paths,
    merge_collections,
    prune_orphaned_paths,
    validate_tag_name,
)


# ---------------------------------------------------------------------------
# validate_tag_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["Sunset", "trip 2024", "a"])
def test_validate_tag_name_accepts_good_names(name):
    assert validate_tag_name(name) is True


@pytest.mark.parametrize(
    "name", ["", "   ", " leading", "trailing ", "with\nnewline", "tab\there", 5, None],
)
def test_validate_tag_name_rejects_bad_names(name):
    assert validate_tag_name(name) is False


# ---------------------------------------------------------------------------
# find_duplicate_names
# ---------------------------------------------------------------------------


def test_find_duplicate_names_case_insensitive():
    # "Foo", "foo", "FOO" collapse to one normalised group; "bar" is unique.
    dups = find_duplicate_names({"Foo": [], "foo": [], "FOO": [], "bar": []})
    assert dups == {"foo": ["FOO", "Foo", "foo"]}
    assert "bar" not in dups


def test_find_duplicate_names_none_when_unique():
    assert find_duplicate_names({"a": [], "b": []}) == {}


# ---------------------------------------------------------------------------
# find_name_collisions
# ---------------------------------------------------------------------------


def test_find_name_collisions():
    tags = {"Trip": [], "People": []}
    albums = {"trip": [], "Places": []}
    assert find_name_collisions(tags, albums) == ["trip"]


def test_find_name_collisions_none():
    assert find_name_collisions({"a": []}, {"b": []}) == []


# ---------------------------------------------------------------------------
# find_orphaned_paths / prune_orphaned_paths
# ---------------------------------------------------------------------------


def test_find_orphaned_paths():
    collection = {"trip": ["/a.png", "/gone.png"], "people": ["/b.png"]}
    existing = {"/a.png", "/b.png"}
    assert find_orphaned_paths(collection, existing) == {"trip": ["/gone.png"]}


def test_prune_orphaned_paths_keeps_empty_collections():
    collection = {"trip": ["/a.png", "/gone.png"], "empty": []}
    pruned = prune_orphaned_paths(collection, {"/a.png"})
    assert pruned == {"trip": ["/a.png"], "empty": []}


def test_prune_does_not_mutate_input():
    collection = {"trip": ["/a.png", "/gone.png"]}
    prune_orphaned_paths(collection, {"/a.png"})
    assert collection == {"trip": ["/a.png", "/gone.png"]}


# ---------------------------------------------------------------------------
# find_empty_collections
# ---------------------------------------------------------------------------


def test_find_empty_collections():
    assert find_empty_collections({"a": [], "b": ["/x.png"], "c": []}) == ["a", "c"]


# ---------------------------------------------------------------------------
# merge_collections
# ---------------------------------------------------------------------------


def test_merge_collections_unions_and_dedupes():
    collection = {"a": ["/1.png", "/2.png"], "b": ["/2.png", "/3.png"]}
    merged = merge_collections(collection, "b", "a")
    assert merged == {"a": ["/1.png", "/2.png", "/3.png"]}
    assert "b" not in merged


def test_merge_collections_into_absent_target_is_rename():
    merged = merge_collections({"a": ["/1.png"]}, "a", "b")
    assert merged == {"b": ["/1.png"]}


def test_merge_collections_noop_when_source_missing_or_same():
    original = {"a": ["/1.png"]}
    assert merge_collections(original, "ghost", "a") == original
    assert merge_collections(original, "a", "a") == original


def test_merge_collections_does_not_mutate_input():
    collection = {"a": ["/1.png"], "b": ["/2.png"]}
    merge_collections(collection, "b", "a")
    assert collection == {"a": ["/1.png"], "b": ["/2.png"]}
