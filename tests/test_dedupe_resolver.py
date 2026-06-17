"""Tests for the duplicate-resolution ranking."""
from __future__ import annotations

from Imervue.library.dedupe_resolver import (
    Candidate,
    plan_discards,
    resolve_group,
    resolve_groups,
)


def _c(path, w, h, size):
    return Candidate(path=path, width=w, height=h, size_bytes=size)


class TestResolveGroup:
    def test_highest_resolution_is_kept(self):
        keep, discard = resolve_group([_c("a", 100, 100, 500), _c("b", 200, 200, 100)])
        assert keep.path == "b"
        assert [d.path for d in discard] == ["a"]

    def test_equal_resolution_keeps_larger_file(self):
        keep, _ = resolve_group([_c("a", 100, 100, 500), _c("b", 100, 100, 900)])
        assert keep.path == "b"

    def test_full_tie_breaks_on_smallest_path(self):
        keep, _ = resolve_group([_c("z", 100, 100, 500), _c("a", 100, 100, 500)])
        assert keep.path == "a"

    def test_empty_group_keeps_nothing(self):
        assert resolve_group([]) == (None, [])

    def test_single_member_kept_with_no_discards(self):
        keep, discard = resolve_group([_c("a", 10, 10, 10)])
        assert keep.path == "a"
        assert discard == []


class TestResolveGroups:
    def test_skips_groups_with_no_keeper(self):
        resolved = resolve_groups([[], [_c("a", 10, 10, 10), _c("b", 20, 20, 20)]])
        assert len(resolved) == 1
        assert resolved[0][0].path == "b"
        assert [d.path for d in resolved[0][1]] == ["a"]


class TestPlanDiscards:
    def test_flattens_discards_across_groups(self):
        groups = [
            [_c("a", 100, 100, 100), _c("b", 200, 200, 100)],   # keep b
            [_c("c", 50, 50, 50), _c("d", 50, 50, 50)],         # keep c (path)
        ]
        assert sorted(plan_discards(groups)) == ["a", "d"]

    def test_no_groups_is_empty(self):
        assert plan_discards([]) == []
