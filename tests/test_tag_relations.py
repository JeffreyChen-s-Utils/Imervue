"""Tests for tag co-occurrence / related-tag suggestions."""
from __future__ import annotations

import pytest

from Imervue.library import image_index
from Imervue.library.tag_relations import related_tags, suggest_related


# ---------------------------------------------------------------------------
# Pure ranking core
# ---------------------------------------------------------------------------


def test_related_tags_ranks_by_shared_count():
    membership = {
        "beach": {"1", "2", "3"},
        "sunset": {"2", "3", "4"},
        "indoor": {"5"},
    }
    assert related_tags("beach", membership) == [("sunset", 2)]


def test_related_tags_excludes_target_itself():
    membership = {"a": {"1", "2"}, "b": {"1"}}
    assert [tag for tag, _ in related_tags("a", membership)] == ["b"]


def test_related_tags_sorts_by_count_then_name():
    membership = {
        "target": {"1", "2"},
        "zeta": {"1"},      # shares 1
        "alpha": {"2"},     # shares 1
        "both": {"1", "2"},  # shares 2
    }
    assert related_tags("target", membership) == [
        ("both", 2), ("alpha", 1), ("zeta", 1)]


def test_related_tags_limit_caps_results():
    membership = {
        "target": {"1", "2", "3"},
        "a": {"1"}, "b": {"2"}, "c": {"3"},
    }
    assert len(related_tags("target", membership, limit=2)) == 2


def test_related_tags_unknown_or_empty_target():
    assert related_tags("missing", {"a": {"1"}}) == []
    assert related_tags("t", {"t": set()}) == []


# ---------------------------------------------------------------------------
# Live wiring over an isolated index
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def test_suggest_related_reads_from_index():
    for path in ("a.png", "b.png"):
        image_index.add_image_tag(path, "beach")
        image_index.add_image_tag(path, "sunset")
    image_index.add_image_tag("c.png", "indoor")  # unrelated
    suggestions = suggest_related("beach")
    assert suggestions[0][0] == "sunset"
    assert dict(suggestions).get("indoor") is None
