"""Pure helpers behind the Tags & Albums dialog (``gui/tag_album_logic.py``)."""
from __future__ import annotations

import pytest

from Imervue.gui.tag_album_logic import (
    cleanup_summary,
    collection_rows,
    entered_name,
    existing_member_paths,
    viewable_images,
)
from Imervue.user_settings.tag_validator import CleanupPlan


@pytest.mark.parametrize(("text", "ok", "expected"), [
    ("  Sea ", True, "Sea"),
    ("Sea", True, "Sea"),
    ("", True, None),
    ("   ", True, None),
    ("Sea", False, None),
    ("", False, None),
])
def test_entered_name(text, ok, expected):
    assert entered_name(text, ok) == expected


def test_collection_rows_are_sorted_and_counted():
    assert collection_rows({"b": ["1", "2"], "A": [], "a": ["x"]}) == [
        ("A  (0)", "A"), ("a  (1)", "a"), ("b  (2)", "b")]


def test_collection_rows_of_an_empty_collection():
    assert collection_rows({}) == []


def test_viewable_images_keep_order_and_drop_missing():
    files = {"c", "a"}
    assert viewable_images(["a", "b", "c"], is_file=files.__contains__) == ["a", "c"]
    assert viewable_images([], is_file=files.__contains__) == []


def test_viewable_images_default_checks_the_disk(tmp_path):
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    assert viewable_images([str(tmp_path), str(kept), str(tmp_path / "gone")]) == [str(kept)]


def test_existing_member_paths_spans_every_collection():
    present = {"a", "c"}
    tags = {"T": ["a", "b"], "U": []}
    albums = {"A": ["a", "c", "d"]}
    assert existing_member_paths(tags, albums, exists=present.__contains__) == {"a", "c"}
    assert existing_member_paths(exists=present.__contains__) == set()


def test_existing_member_paths_default_checks_the_disk(tmp_path):
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    found = existing_member_paths({"T": [str(kept), str(tmp_path / "gone")]}, {"A": [str(tmp_path)]})
    assert found == {str(kept), str(tmp_path)}


def test_cleanup_summary_totals_orphans_and_lists_merges():
    plans = (CleanupPlan(2, [("Foo", "foo")]), CleanupPlan(1, [("a", "A"), ("b", "B")]))
    assert cleanup_summary(plans) == (3, ["Foo → foo", "a → A", "b → B"])


def test_cleanup_summary_accepts_a_one_shot_iterable():
    plans = iter([CleanupPlan(1), CleanupPlan(0, [("x", "X")])])
    assert cleanup_summary(plans) == (1, ["x → X"])
    assert cleanup_summary([]) == (0, [])
