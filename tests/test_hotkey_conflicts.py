"""Tests for hotkey conflict detection."""
from __future__ import annotations

from Imervue.desktop_pet.hotkey_conflicts import (
    canonical_spec,
    find_conflicts,
    has_conflicts,
)


# ---------------------------------------------------------------------------
# canonical_spec
# ---------------------------------------------------------------------------


def test_canonical_is_modifier_order_independent():
    assert canonical_spec("ctrl+shift+p") == canonical_spec("shift+ctrl+p")


def test_canonical_collapses_case_and_aliases():
    assert canonical_spec("Ctrl+P") == canonical_spec("control+p")


def test_canonical_distinguishes_different_keys():
    assert canonical_spec("ctrl+p") != canonical_spec("ctrl+q")


def test_canonical_invalid_spec_is_none():
    assert canonical_spec("") is None
    assert canonical_spec("ctrl+shift") is None  # modifier-only


# ---------------------------------------------------------------------------
# find_conflicts
# ---------------------------------------------------------------------------


def test_no_conflicts_when_all_distinct():
    assert find_conflicts({"a": "ctrl+p", "b": "ctrl+q"}) == {}


def test_detects_same_chord_two_actions():
    conflicts = find_conflicts({"toggle": "ctrl+p", "speak": "ctrl+p"})
    assert len(conflicts) == 1
    actions = next(iter(conflicts.values()))
    assert set(actions) == {"toggle", "speak"}


def test_detects_conflict_despite_different_spelling():
    conflicts = find_conflicts({
        "a": "Ctrl+Shift+P", "b": "shift+control+p",
    })
    assert len(conflicts) == 1
    assert set(next(iter(conflicts.values()))) == {"a", "b"}


def test_ignores_invalid_specs():
    assert find_conflicts({"a": "ctrl+p", "b": "", "c": "nonsense+"}) == {}


def test_action_order_preserved_in_report():
    conflicts = find_conflicts({"first": "ctrl+p", "second": "ctrl+p"})
    assert next(iter(conflicts.values())) == ["first", "second"]


# ---------------------------------------------------------------------------
# has_conflicts
# ---------------------------------------------------------------------------


def test_has_conflicts_boolean():
    assert has_conflicts({"a": "ctrl+p", "b": "ctrl+p"}) is True
    assert has_conflicts({"a": "ctrl+p", "b": "ctrl+q"}) is False
    assert has_conflicts({}) is False
