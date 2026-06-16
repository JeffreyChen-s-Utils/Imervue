"""Tests for the pure crop-geometry helpers."""
from __future__ import annotations

import pytest

from Imervue.image.crop_geometry import (
    ASPECT_PRESETS,
    centered_aspect_crop,
    clamp_crop_fraction,
    parse_aspect,
    thirds_lines,
)


class TestParseAspect:
    def test_free_and_invalid_return_none(self):
        assert parse_aspect("free") is None
        assert parse_aspect("") is None
        assert parse_aspect("16-9") is None
        assert parse_aspect("a:b") is None
        assert parse_aspect("0:1") is None

    @pytest.mark.parametrize("label,expected", [
        ("1:1", 1.0), ("16:9", 16 / 9), ("4:5", 0.8), ("2:3", 2 / 3),
    ])
    def test_valid_ratios(self, label, expected):
        assert parse_aspect(label) == pytest.approx(expected)

    def test_every_preset_parses_or_is_free(self):
        for label in ASPECT_PRESETS:
            result = parse_aspect(label)
            assert (label == "free") == (result is None)


class TestCenteredAspectCrop:
    def test_square_crop_in_wide_image_is_height_limited(self):
        # 16:9 image, 1:1 crop → full height, centred narrower width.
        x, y, w, h = centered_aspect_crop(16 / 9, 1.0)
        assert h == pytest.approx(1.0)
        assert w == pytest.approx(9 / 16)
        assert x == pytest.approx((1 - 9 / 16) / 2)
        assert y == pytest.approx(0.0)

    def test_wide_crop_in_square_image_is_width_limited(self):
        x, y, w, h = centered_aspect_crop(1.0, 16 / 9)
        assert w == pytest.approx(1.0)
        assert h == pytest.approx(9 / 16)
        assert y == pytest.approx((1 - 9 / 16) / 2)

    def test_matching_aspect_is_full_frame(self):
        assert centered_aspect_crop(1.5, 1.5) == pytest.approx((0.0, 0.0, 1.0, 1.0))

    def test_non_positive_inputs_collapse_to_identity(self):
        assert centered_aspect_crop(0.0, 1.0) == (0.0, 0.0, 1.0, 1.0)
        assert centered_aspect_crop(1.0, 0.0) == (0.0, 0.0, 1.0, 1.0)


class TestClampCropFraction:
    def test_in_range_unchanged(self):
        assert clamp_crop_fraction(0.1, 0.2, 0.5, 0.5) == (0.1, 0.2, 0.5, 0.5)

    def test_extent_trimmed_to_edge(self):
        assert clamp_crop_fraction(0.8, 0.0, 0.5, 1.0) == (0.8, 0.0, pytest.approx(0.2), 1.0)

    def test_negative_origin_and_size_clamped(self):
        assert clamp_crop_fraction(-0.5, -0.5, -1.0, -1.0) == (0.0, 0.0, 0.0, 0.0)


class TestThirdsLines:
    def test_full_frame_thirds(self):
        verticals, horizontals = thirds_lines(0.0, 0.0, 1.0, 1.0)
        assert verticals == pytest.approx((1 / 3, 2 / 3))
        assert horizontals == pytest.approx((1 / 3, 2 / 3))

    def test_offset_rect_thirds(self):
        verticals, horizontals = thirds_lines(0.2, 0.4, 0.6, 0.3)
        assert verticals == pytest.approx((0.4, 0.6))
        assert horizontals == pytest.approx((0.5, 0.6))
