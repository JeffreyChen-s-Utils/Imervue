"""Tests for best-of-group culling."""
from __future__ import annotations

import pytest

from Imervue.library.group_cull import (
    CullDecision,
    best_in_group,
    plan_group_cull,
    select_best_per_group,
)


# ---------------------------------------------------------------------------
# best_in_group
# ---------------------------------------------------------------------------


def test_best_in_group_picks_max_score():
    scores = {"a.jpg": 0.2, "b.jpg": 0.9, "c.jpg": 0.5}
    assert best_in_group(["a.jpg", "b.jpg", "c.jpg"], scores) == "b.jpg"


def test_best_in_group_ties_keep_first():
    scores = {"a.jpg": 0.9, "b.jpg": 0.9}
    assert best_in_group(["a.jpg", "b.jpg"], scores) == "a.jpg"


def test_best_in_group_missing_scores_are_lowest():
    scores = {"b.jpg": 0.1}  # a.jpg unscored
    assert best_in_group(["a.jpg", "b.jpg"], scores) == "b.jpg"


def test_best_in_group_all_unscored_keeps_first():
    assert best_in_group(["a.jpg", "b.jpg"], {}) == "a.jpg"


def test_best_in_group_empty_raises():
    with pytest.raises(ValueError, match="empty group"):
        best_in_group([], {"a": 1.0})


# ---------------------------------------------------------------------------
# select_best_per_group
# ---------------------------------------------------------------------------


def test_select_best_per_group():
    groups = [["a.jpg", "b.jpg"], ["c.jpg"]]
    scores = {"a.jpg": 0.1, "b.jpg": 0.8, "c.jpg": 0.5}
    decisions = select_best_per_group(groups, scores)
    assert decisions == [
        CullDecision(keep="b.jpg", reject=("a.jpg",)),
        CullDecision(keep="c.jpg", reject=()),
    ]


def test_select_skips_empty_groups():
    decisions = select_best_per_group([[], ["a.jpg"]], {"a.jpg": 1.0})
    assert [d.keep for d in decisions] == ["a.jpg"]


def test_cull_decision_is_frozen():
    decision = CullDecision(keep="a.jpg", reject=("b.jpg",))
    with pytest.raises((AttributeError, TypeError)):
        decision.keep = "c.jpg"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# plan_group_cull
# ---------------------------------------------------------------------------


def test_plan_group_cull_flattens():
    groups = [["a.jpg", "b.jpg"], ["c.jpg", "d.jpg", "e.jpg"]]
    scores = {"a.jpg": 0.9, "b.jpg": 0.1, "c.jpg": 0.2, "d.jpg": 0.3, "e.jpg": 0.9}
    picks, rejects = plan_group_cull(groups, scores)
    assert picks == ["a.jpg", "e.jpg"]
    assert rejects == ["b.jpg", "c.jpg", "d.jpg"]


def test_plan_partitions_every_path_exactly_once():
    groups = [["a", "b", "c"], ["d"], ["e", "f"]]
    scores = {"a": 1, "b": 2, "c": 3, "d": 1, "e": 5, "f": 4}
    picks, rejects = plan_group_cull(groups, scores)
    all_paths = {p for group in groups for p in group}
    assert set(picks).isdisjoint(rejects)
    assert set(picks) | set(rejects) == all_paths
    assert len(picks) + len(rejects) == len(all_paths)


def test_plan_empty_input():
    assert plan_group_cull([], {}) == ([], [])
