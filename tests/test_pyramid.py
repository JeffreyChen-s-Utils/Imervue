"""Tests for DeepZoomImage pyramid."""

import numpy as np

from Imervue.image.pyramid import DeepZoomImage


class TestDeepZoomImage:
    def test_single_level_small_image(self):
        """Image smaller than 512 should have only 1 level."""
        img = np.zeros((256, 256, 4), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        assert len(dzi.levels) == 1
        assert dzi.levels[0].shape == (256, 256, 4)

    def test_multiple_levels(self):
        """Image larger than 512 should have multiple levels."""
        img = np.zeros((2048, 2048, 4), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        assert len(dzi.levels) > 1
        # Each level should be roughly half the previous
        for i in range(1, len(dzi.levels)):
            prev_h = dzi.levels[i - 1].shape[0]
            curr_h = dzi.levels[i].shape[0]
            assert curr_h < prev_h

    def test_levels_decreasing_size(self):
        """Each level should be smaller than the previous."""
        img = np.random.randint(0, 256, (4096, 4096, 3), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        for i in range(1, len(dzi.levels)):
            assert dzi.levels[i].shape[0] < dzi.levels[i - 1].shape[0]
            assert dzi.levels[i].shape[1] < dzi.levels[i - 1].shape[1]

    def test_get_level_zoom_1(self):
        """Zoom 1.0 should return level 0 (full resolution)."""
        img = np.zeros((2048, 2048, 4), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        level, data = dzi.get_level(1.0)
        assert level == 0

    def test_get_level_zoom_out(self):
        """Zooming out should return higher level numbers."""
        img = np.zeros((4096, 4096, 4), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        l1, _ = dzi.get_level(1.0)
        l2, _ = dzi.get_level(0.25)
        assert l2 >= l1

    def test_get_level_clamped(self):
        """Level should never exceed the last level index."""
        img = np.zeros((2048, 2048, 4), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        level, data = dzi.get_level(0.001)
        assert level == len(dzi.levels) - 1

    def test_rgb_input(self):
        """3-channel input should work."""
        img = np.zeros((1024, 1024, 3), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        assert len(dzi.levels) >= 1
        assert dzi.levels[0].shape[2] == 3

    def test_rgba_input(self):
        """4-channel input should work."""
        img = np.zeros((1024, 1024, 4), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        assert len(dzi.levels) >= 1
        assert dzi.levels[0].shape[2] == 4

    def test_non_square_image(self):
        """Non-square images should work correctly."""
        img = np.zeros((2048, 512, 3), dtype=np.uint8)
        dzi = DeepZoomImage(img)
        # Only one dimension > 512, so should still build some levels
        assert len(dzi.levels) >= 1
