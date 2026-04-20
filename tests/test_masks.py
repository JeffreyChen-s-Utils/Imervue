"""Tests for local adjustment masks."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import masks


class TestMaskAdjustments:
    def test_is_zero_default(self):
        assert masks.MaskAdjustments().is_zero()

    def test_non_zero(self):
        adj = masks.MaskAdjustments(exposure=0.5)
        assert not adj.is_zero()

    def test_round_trip(self):
        adj = masks.MaskAdjustments(
            exposure=0.5, brightness=-0.2, contrast=0.1,
            saturation=0.3, temperature=-0.1, tint=0.05,
        )
        back = masks.MaskAdjustments.from_dict(adj.to_dict())
        assert back == adj


class TestMask:
    def test_round_trip(self):
        m = masks.Mask(
            mask_type="radial",
            params={"cx": 100.0, "cy": 50.0, "rx": 80.0, "ry": 40.0},
            adjustments=masks.MaskAdjustments(exposure=0.4),
            invert=True,
            feather=0.3,
        )
        back = masks.Mask.from_dict(m.to_dict())
        assert back.mask_type == "radial"
        assert back.invert is True
        assert back.feather == pytest.approx(0.3)
        assert back.adjustments.exposure == pytest.approx(0.4)

    def test_unknown_type_falls_back(self):
        m = masks.Mask.from_dict({"type": "whatever"})
        assert m.mask_type == "brush"


class TestGenerateAlpha:
    def test_brush_alpha_is_positive_near_point(self):
        m = masks.Mask(
            mask_type="brush",
            params={"points": [{"x": 20.0, "y": 20.0, "r": 10.0}]},
            feather=0.5,
        )
        alpha = masks.generate_alpha((40, 40), m)
        assert alpha[20, 20] > 0.9
        assert alpha[0, 0] < 0.1

    def test_radial_invert_flips_inside_outside(self):
        m = masks.Mask(
            mask_type="radial",
            params={"cx": 20, "cy": 20, "rx": 10, "ry": 10},
            feather=0.0,
            invert=True,
        )
        alpha = masks.generate_alpha((40, 40), m)
        # With invert and no feather, centre should be ~0, far corner ~1.
        assert alpha[20, 20] < 0.05
        assert alpha[0, 0] > 0.9

    def test_linear_gradient_monotonic(self):
        m = masks.Mask(
            mask_type="linear",
            params={"x0": 0, "y0": 20, "x1": 40, "y1": 20},
            feather=1.0,
        )
        alpha = masks.generate_alpha((40, 40), m)
        # Left edge should be more opaque than the right.
        assert alpha[20, 0] > alpha[20, 39]

    def test_unknown_type_returns_zeros(self):
        m = masks.Mask(mask_type="brush")
        m.mask_type = "nonsense"   # bypass validation
        alpha = masks.generate_alpha((10, 10), m)
        assert (alpha == 0).all()


class TestApplyMasks:
    def test_empty_list_passes_through(self):
        arr = np.full((20, 20, 4), 100, dtype=np.uint8)
        out = masks.apply_masks(arr, [])
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((20, 20, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            masks.apply_masks(arr, [masks.Mask(mask_type="brush")])

    def test_brush_brightens_only_inside_region(self):
        arr = np.full((40, 40, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        m = masks.Mask(
            mask_type="brush",
            params={"points": [{"x": 20.0, "y": 20.0, "r": 5.0}]},
            adjustments=masks.MaskAdjustments(brightness=0.5),
            feather=0.2,
        )
        out = masks.apply_masks(arr, [m])
        assert int(out[20, 20, 0]) > 130
        assert int(out[0, 0, 0]) == 100

    def test_zero_adjustments_skipped(self):
        arr = np.full((20, 20, 4), 100, dtype=np.uint8)
        m = masks.Mask(
            mask_type="brush",
            params={"points": [{"x": 10.0, "y": 10.0, "r": 5.0}]},
        )
        out = masks.apply_masks(arr, [m])
        assert np.array_equal(out, arr)


class TestRoundTripLists:
    def test_masks_from_dict_list_skips_garbage(self):
        items = [
            {"type": "brush", "params": {"points": []}},
            "not a dict",
            {},
            {"type": "radial"},
        ]
        out = masks.masks_from_dict_list(items)
        assert len(out) == 3
