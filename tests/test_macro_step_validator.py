"""Tests for macro step validation / tidying."""
from __future__ import annotations

from Imervue.macros.macro_manager import MacroStep
from Imervue.macros.macro_step_validator import (
    CODE_BAD_KWARGS,
    CODE_UNKNOWN_ACTION,
    deduplicate_consecutive,
    find_redundant_tag_pairs,
    find_unknown_actions,
    validate_steps,
)

_KNOWN = {"set_rating", "add_tag", "remove_tag"}


# ---------------------------------------------------------------------------
# validate_steps
# ---------------------------------------------------------------------------


def test_validate_clean_steps():
    steps = [MacroStep("set_rating", {"rating": 5}), MacroStep("add_tag", {"tag": "x"})]
    assert validate_steps(steps, _KNOWN) == []


def test_validate_flags_unknown_action():
    issues = validate_steps([MacroStep("frobnicate", {})], _KNOWN)
    assert len(issues) == 1
    assert issues[0].code == CODE_UNKNOWN_ACTION
    assert issues[0].index == 0


def test_validate_flags_bad_kwargs():
    issues = validate_steps([MacroStep("set_rating", ["not", "a", "dict"])], _KNOWN)
    assert issues[0].code == CODE_BAD_KWARGS


# ---------------------------------------------------------------------------
# find_unknown_actions
# ---------------------------------------------------------------------------


def test_find_unknown_actions_distinct_first_seen():
    steps = [
        MacroStep("ghost", {}),
        MacroStep("set_rating", {"rating": 1}),
        MacroStep("phantom", {}),
        MacroStep("ghost", {}),
    ]
    assert find_unknown_actions(steps, _KNOWN) == ["ghost", "phantom"]


def test_find_unknown_actions_none():
    assert find_unknown_actions([MacroStep("add_tag", {"tag": "x"})], _KNOWN) == []


# ---------------------------------------------------------------------------
# deduplicate_consecutive
# ---------------------------------------------------------------------------


def test_dedup_collapses_runs():
    steps = [
        MacroStep("set_rating", {"rating": 5}),
        MacroStep("set_rating", {"rating": 5}),
        MacroStep("set_rating", {"rating": 3}),
    ]
    out = deduplicate_consecutive(steps)
    assert [s.kwargs["rating"] for s in out] == [5, 3]


def test_dedup_keeps_non_adjacent_duplicates():
    a = MacroStep("add_tag", {"tag": "x"})
    b = MacroStep("set_rating", {"rating": 1})
    out = deduplicate_consecutive([a, b, a])
    assert len(out) == 3  # a...a are not adjacent


def test_dedup_empty():
    assert deduplicate_consecutive([]) == []


# ---------------------------------------------------------------------------
# find_redundant_tag_pairs
# ---------------------------------------------------------------------------


def test_redundant_add_then_remove_same_tag():
    steps = [
        MacroStep("add_tag", {"tag": "trip"}),
        MacroStep("set_rating", {"rating": 5}),
        MacroStep("remove_tag", {"tag": "trip"}),
    ]
    assert find_redundant_tag_pairs(steps) == [(0, 2)]


def test_no_pair_for_different_tags():
    steps = [
        MacroStep("add_tag", {"tag": "a"}),
        MacroStep("remove_tag", {"tag": "b"}),
    ]
    assert find_redundant_tag_pairs(steps) == []


def test_no_pair_for_add_without_remove():
    steps = [MacroStep("add_tag", {"tag": "a"}), MacroStep("add_tag", {"tag": "a"})]
    assert find_redundant_tag_pairs(steps) == []


def test_remove_then_add_is_not_flagged():
    # Only add-then-remove cancels for our purposes (the tag ends up absent).
    steps = [
        MacroStep("remove_tag", {"tag": "a"}),
        MacroStep("add_tag", {"tag": "a"}),
    ]
    assert find_redundant_tag_pairs(steps) == []
