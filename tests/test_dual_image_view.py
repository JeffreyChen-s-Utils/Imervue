"""Tests for DualImageView pair navigation and RTL swap."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def dual(qapp):
    from Imervue.gui.dual_image_view import DualImageView
    mw = MagicMock()
    mw.viewer.model.images = []
    mw.viewer.current_index = 0
    return DualImageView(mw)


class TestDualImageView:
    def test_default_mode_is_split(self, dual):
        assert dual.mode == "split"

    def test_set_mode_valid(self, dual):
        dual.set_mode("manga")
        assert dual.mode == "manga"
        dual.set_mode("manga_rtl")
        assert dual.mode == "manga_rtl"

    def test_set_mode_rejects_invalid(self, dual):
        dual.set_mode("manga")
        dual.set_mode("bogus")
        assert dual.mode == "manga"

    def test_step_pair_advances(self, dual, tmp_path):
        paths = [str(tmp_path / f"img_{i}.png") for i in range(10)]
        dual.set_mode("manga")
        new_idx = dual.step_pair_in_list(paths, current_idx=0, step=2)
        assert new_idx == 2

    def test_step_pair_clamps_at_end(self, dual, tmp_path):
        paths = [str(tmp_path / f"img_{i}.png") for i in range(4)]
        new_idx = dual.step_pair_in_list(paths, current_idx=3, step=2)
        assert new_idx == 3  # Clamped — only 4 images

    def test_step_pair_clamps_at_start(self, dual, tmp_path):
        paths = [str(tmp_path / f"img_{i}.png") for i in range(4)]
        new_idx = dual.step_pair_in_list(paths, current_idx=0, step=-2)
        assert new_idx == 0

    def test_step_pair_empty_list_is_noop(self, dual):
        new_idx = dual.step_pair_in_list([], current_idx=0, step=2)
        assert new_idx == 0

    def test_set_pair_stores_paths(self, dual, tmp_path):
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        dual.set_pair(a, b)
        assert dual._left_path == a
        assert dual._right_path == b

    def test_rtl_swaps_panels_internally(self, dual, tmp_path):
        """RTL mode keeps _left/_right logical but displays right on left panel."""
        a = str(tmp_path / "page1.png")
        b = str(tmp_path / "page2.png")
        dual.set_mode("manga_rtl")
        dual.set_pair(a, b)
        # Logical pair stays the same
        assert dual._left_path == a
        assert dual._right_path == b
