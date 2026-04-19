"""Tests for command-palette fuzzy scoring."""
from __future__ import annotations

import pytest


@pytest.fixture
def cp(qapp):
    from Imervue.gui import command_palette as m
    return m


class TestFuzzyScore:
    def test_empty_query_is_zero(self, cp):
        assert cp.fuzzy_score("", "anything") == 0

    def test_exact_prefix_scores_high(self, cp):
        s_prefix = cp.fuzzy_score("open", "open file")
        s_other = cp.fuzzy_score("open", "close file")
        assert s_prefix > s_other

    def test_subsequence_match_still_scores(self, cp):
        # q=oof should match "open file" as o..p..e..n..f becomes o..f..
        # A weak but non-zero score is fine.
        s = cp.fuzzy_score("of", "open file")
        assert s > 0

    def test_no_match_returns_negative(self, cp):
        assert cp.fuzzy_score("xyzqq", "open file") == -1
