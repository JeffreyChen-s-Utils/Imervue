"""Tests for tag_filter_dialog.combine_sets boolean logic."""
from __future__ import annotations

import pytest


@pytest.fixture
def mod():
    from Imervue.gui import tag_filter_dialog as m
    return m


class TestCombineSets:
    def test_empty_groups_returns_empty(self, mod):
        assert mod.combine_sets([], "or") == set()
        assert mod.combine_sets([], "and") == set()

    def test_or_is_union(self, mod):
        groups = [{"a.png", "b.png"}, {"b.png", "c.png"}]
        assert mod.combine_sets(groups, "or") == {"a.png", "b.png", "c.png"}

    def test_and_is_intersection(self, mod):
        groups = [{"a.png", "b.png"}, {"b.png", "c.png"}]
        assert mod.combine_sets(groups, "and") == {"b.png"}

    def test_and_with_disjoint_is_empty(self, mod):
        groups = [{"a.png"}, {"b.png"}]
        assert mod.combine_sets(groups, "and") == set()

    def test_single_group_both_modes_identical(self, mod):
        groups = [{"a", "b", "c"}]
        assert mod.combine_sets(groups, "and") == {"a", "b", "c"}
        assert mod.combine_sets(groups, "or") == {"a", "b", "c"}

    def test_unknown_mode_falls_back_to_or(self, mod):
        groups = [{"a"}, {"b"}]
        assert mod.combine_sets(groups, "xyz") == {"a", "b"}
