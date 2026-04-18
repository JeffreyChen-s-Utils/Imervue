"""Unit tests for search_dialog's fuzzy-score and highlight helpers."""
from __future__ import annotations

import pytest


@pytest.fixture
def mod(qapp):
    # Import after qapp so the module can rely on Qt being initialised.
    from Imervue.gpu_image_view.actions import search_dialog as m
    return m


class TestFuzzyScore:
    def test_empty_keyword_matches(self, mod):
        rank, idx = mod._fuzzy_score("abc.png", "")
        assert rank == 1
        assert idx == 0

    def test_prefix_is_best_rank(self, mod):
        rank, idx = mod._fuzzy_score("sunset.jpg", "sun")
        assert rank == 0
        assert idx == 0

    def test_substring_is_rank_1(self, mod):
        rank, idx = mod._fuzzy_score("my_sunset.jpg", "sun")
        assert rank == 1
        assert idx == 3

    def test_subsequence_is_rank_2(self, mod):
        rank, idx = mod._fuzzy_score("s_u_n", "sun")
        assert rank == 2
        assert idx == 0

    def test_no_match_is_rank_3(self, mod):
        rank, _ = mod._fuzzy_score("abcdef", "xyz")
        assert rank == 3

    def test_case_sensitivity_expected_lowered_by_caller(self, mod):
        # The helper itself is case-sensitive — callers lowercase both sides.
        rank_upper, _ = mod._fuzzy_score("Sunset", "sun")
        assert rank_upper == 3
        rank_lower, _ = mod._fuzzy_score("sunset", "sun")
        assert rank_lower == 0


class TestHighlightHtml:
    def test_empty_keyword_just_escapes(self, mod):
        assert mod._highlight_html("a<b>c", "") == "a&lt;b&gt;c"

    def test_substring_gets_wrapped(self, mod):
        html = mod._highlight_html("sunset.jpg", "sun")
        assert "<b" in html and "sun" in html
        # Parts before and after should still be present
        assert "set.jpg" in html

    def test_no_match_returns_plain_escaped(self, mod):
        assert mod._highlight_html("abc&def", "zzz") == "abc&amp;def"

    def test_highlight_is_case_insensitive(self, mod):
        html = mod._highlight_html("Sunset", "SUN")
        # Original-case substring preserved inside the bold tag
        assert "Sun" in html
        assert "<b" in html
