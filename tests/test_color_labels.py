"""Tests for the color_labels backend — get/set/toggle/filter."""
from __future__ import annotations

import pytest


@pytest.fixture
def cl():
    from Imervue.user_settings import color_labels as m
    # Isolated via the conftest settings fixture — each test gets a clean dict.
    return m


class TestSetGet:
    def test_get_missing_returns_none(self, cl):
        assert cl.get_color_label("ghost.png") is None

    def test_set_then_get_round_trip(self, cl):
        assert cl.set_color_label("a.png", "red") is True
        assert cl.get_color_label("a.png") == "red"

    def test_set_same_color_is_noop(self, cl):
        cl.set_color_label("a.png", "blue")
        assert cl.set_color_label("a.png", "blue") is False

    def test_set_changes_color(self, cl):
        cl.set_color_label("a.png", "red")
        assert cl.set_color_label("a.png", "green") is True
        assert cl.get_color_label("a.png") == "green"

    def test_invalid_color_clears(self, cl):
        cl.set_color_label("a.png", "red")
        assert cl.set_color_label("a.png", "chartreuse") is True  # unknown → clear
        assert cl.get_color_label("a.png") is None

    def test_none_color_clears(self, cl):
        cl.set_color_label("a.png", "red")
        assert cl.set_color_label("a.png", None) is True
        assert cl.get_color_label("a.png") is None

    def test_empty_path_is_rejected(self, cl):
        assert cl.set_color_label("", "red") is False
        assert cl.get_color_label("") is None

    def test_clear_on_unlabelled_is_noop(self, cl):
        assert cl.clear_color_label("never_labelled.png") is False


class TestToggle:
    def test_toggle_sets_when_unset(self, cl):
        result = cl.toggle_color_label("a.png", "red")
        assert result == "red"
        assert cl.get_color_label("a.png") == "red"

    def test_toggle_same_clears(self, cl):
        cl.set_color_label("a.png", "red")
        result = cl.toggle_color_label("a.png", "red")
        assert result is None
        assert cl.get_color_label("a.png") is None

    def test_toggle_different_replaces(self, cl):
        cl.set_color_label("a.png", "red")
        result = cl.toggle_color_label("a.png", "blue")
        assert result == "blue"
        assert cl.get_color_label("a.png") == "blue"

    def test_toggle_invalid_color_is_noop(self, cl):
        cl.set_color_label("a.png", "red")
        result = cl.toggle_color_label("a.png", "magenta")
        assert result == "red"


class TestPalette:
    def test_all_colors_have_rgb(self, cl):
        for name in cl.COLORS:
            assert name in cl.COLOR_RGB
            r, g, b = cl.COLOR_RGB[name]
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255


class TestPathsWithLabel:
    def test_empty_store(self, cl):
        assert cl.paths_with_label() == []
        assert cl.paths_with_label("red") == []

    def test_any_returns_all(self, cl):
        cl.set_color_label("a.png", "red")
        cl.set_color_label("b.png", "blue")
        assert set(cl.paths_with_label()) == {"a.png", "b.png"}

    def test_specific_filters(self, cl):
        cl.set_color_label("a.png", "red")
        cl.set_color_label("b.png", "blue")
        cl.set_color_label("c.png", "red")
        assert set(cl.paths_with_label("red")) == {"a.png", "c.png"}

    def test_invalid_color_returns_empty(self, cl):
        cl.set_color_label("a.png", "red")
        assert cl.paths_with_label("cyan") == []


class TestFilterByColor:
    def test_empty_color_returns_all(self, cl):
        paths = ["a.png", "b.png"]
        assert cl.filter_by_color(paths, None) == paths
        assert cl.filter_by_color(paths, "") == paths

    def test_color_filter_keeps_matches(self, cl):
        cl.set_color_label("a.png", "red")
        cl.set_color_label("b.png", "blue")
        result = cl.filter_by_color(["a.png", "b.png", "c.png"], "red")
        assert result == ["a.png"]

    def test_any_filter(self, cl):
        cl.set_color_label("a.png", "red")
        result = cl.filter_by_color(["a.png", "b.png"], "any")
        assert result == ["a.png"]

    def test_none_filter(self, cl):
        cl.set_color_label("a.png", "red")
        result = cl.filter_by_color(["a.png", "b.png"], "none")
        assert result == ["b.png"]

    def test_unknown_color_passes_through(self, cl):
        paths = ["a.png", "b.png"]
        assert cl.filter_by_color(paths, "cyan") == paths

    def test_preserves_order(self, cl):
        cl.set_color_label("c.png", "red")
        cl.set_color_label("a.png", "red")
        cl.set_color_label("b.png", "red")
        result = cl.filter_by_color(["a.png", "b.png", "c.png"], "red")
        assert result == ["a.png", "b.png", "c.png"]  # Input order kept
