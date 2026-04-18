"""Unit tests for advanced_filter_dialog.matches / apply_filter."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def mod():
    from Imervue.gui import advanced_filter_dialog as m
    return m


@pytest.fixture
def landscape_png(tmp_path):
    p = tmp_path / "land.png"
    Image.fromarray(np.zeros((50, 200, 3), dtype=np.uint8)).save(str(p))
    return str(p)


@pytest.fixture
def portrait_png(tmp_path):
    p = tmp_path / "port.png"
    Image.fromarray(np.zeros((200, 50, 3), dtype=np.uint8)).save(str(p))
    return str(p)


@pytest.fixture
def square_png(tmp_path):
    p = tmp_path / "square.png"
    Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8)).save(str(p))
    return str(p)


class TestFilterCriteria:
    def test_empty_criteria_is_inactive(self, mod):
        c = mod.FilterCriteria()
        assert not c.any_active()

    def test_any_field_is_active(self, mod):
        assert mod.FilterCriteria(min_width=100).any_active()
        assert mod.FilterCriteria(orientation="square").any_active()


class TestMatches:
    def test_empty_criteria_always_matches(self, mod, landscape_png):
        assert mod.matches(landscape_png, mod.FilterCriteria()) is True

    def test_min_width_filters(self, mod, landscape_png):
        assert mod.matches(landscape_png, mod.FilterCriteria(min_width=300)) is False
        assert mod.matches(landscape_png, mod.FilterCriteria(min_width=100)) is True

    def test_orientation_landscape(self, mod, landscape_png, portrait_png, square_png):
        crit = mod.FilterCriteria(orientation="landscape")
        assert mod.matches(landscape_png, crit) is True
        assert mod.matches(portrait_png, crit) is False
        assert mod.matches(square_png, crit) is False

    def test_orientation_square(self, mod, square_png, landscape_png):
        crit = mod.FilterCriteria(orientation="square")
        assert mod.matches(square_png, crit) is True
        assert mod.matches(landscape_png, crit) is False

    def test_size_bounds(self, mod, landscape_png):
        size_kb = os.path.getsize(landscape_png) / 1024
        # Way above actual size → should fail
        crit_min = mod.FilterCriteria(min_size_kb=int(size_kb + 1000))
        assert mod.matches(landscape_png, crit_min) is False
        # Huge max → passes
        crit_max = mod.FilterCriteria(max_size_kb=int(size_kb + 1000))
        assert mod.matches(landscape_png, crit_max) is True

    def test_date_bounds(self, mod, landscape_png):
        now = datetime.now()
        # File was just created, so "after now - 1 day" should match
        crit_after = mod.FilterCriteria(after_date=now - timedelta(days=1))
        assert mod.matches(landscape_png, crit_after) is True
        # "before 10 years ago" should fail
        crit_before = mod.FilterCriteria(before_date=now - timedelta(days=3650))
        assert mod.matches(landscape_png, crit_before) is False

    def test_missing_file_returns_false(self, mod, tmp_path):
        ghost = str(tmp_path / "ghost.png")
        # Empty criteria passes through even for missing files (short-circuit).
        # With active criteria, missing file must return False.
        crit = mod.FilterCriteria(min_width=1)
        assert mod.matches(ghost, crit) is False


class TestApplyFilter:
    def test_filter_preserves_order(self, mod, landscape_png, portrait_png, square_png):
        paths = [landscape_png, portrait_png, square_png]
        crit = mod.FilterCriteria(orientation="landscape")
        assert mod.apply_filter(paths, crit) == [landscape_png]

    def test_empty_criteria_returns_all(self, mod, landscape_png, portrait_png):
        crit = mod.FilterCriteria()
        assert mod.apply_filter([landscape_png, portrait_png], crit) == [
            landscape_png, portrait_png,
        ]
