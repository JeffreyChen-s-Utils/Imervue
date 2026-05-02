"""Tests for Blend-If — luminance-range layer visibility gating."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.blend_if import BlendIf, compute_blend_if_mask
from Imervue.paint.document import PaintDocument


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# BlendIf dataclass
# ---------------------------------------------------------------------------


def test_blend_if_default_is_permissive():
    b = BlendIf()
    assert b.this_min == 0
    assert b.this_max == 255


def test_blend_if_is_frozen():
    b = BlendIf()
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.this_min = 100  # type: ignore[misc]


def test_blend_if_rejects_out_of_range():
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        BlendIf(this_min=300)


def test_blend_if_rejects_negative_feather():
    with pytest.raises(ValueError, match="feather"):
        BlendIf(this_min_feather=-1)


def test_blend_if_rejects_inverted_range():
    with pytest.raises(ValueError, match="this_min"):
        BlendIf(this_min=200, this_max=100)


def test_blend_if_round_trip_via_dict():
    b = BlendIf(
        this_min=50, this_max=200,
        this_min_feather=10, this_max_feather=20,
        underlying_min=80, underlying_max=180,
    )
    rebuilt = BlendIf.from_dict(b.to_dict())
    assert rebuilt == b


def test_blend_if_from_dict_clamps_corrupt_values():
    rebuilt = BlendIf.from_dict({
        "this_min": 999, "this_max": -50,
    })
    # 999 → 255, -50 → 0; min > max collapses to common value.
    assert 0 <= rebuilt.this_min <= rebuilt.this_max <= 255


# ---------------------------------------------------------------------------
# compute_blend_if_mask — this layer
# ---------------------------------------------------------------------------


def test_blend_if_default_passes_everything():
    img = _solid((128, 128, 128))
    mask = compute_blend_if_mask(img, None, BlendIf())
    np.testing.assert_array_equal(mask, np.ones_like(mask))


def test_blend_if_this_min_hides_dark_pixels():
    """A pixel below this_min with no feather drops to 0 alpha."""
    img = _solid((20, 20, 20))   # luminance ~20
    mask = compute_blend_if_mask(img, None, BlendIf(this_min=100))
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


def test_blend_if_this_max_hides_bright_pixels():
    img = _solid((250, 250, 250))   # luminance ~250
    mask = compute_blend_if_mask(img, None, BlendIf(this_max=100))
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


def test_blend_if_this_inside_band_passes():
    img = _solid((128, 128, 128))   # luminance 128
    mask = compute_blend_if_mask(
        img, None, BlendIf(this_min=50, this_max=200),
    )
    np.testing.assert_array_equal(mask, np.ones_like(mask))


def test_blend_if_this_min_feather_produces_intermediate_alpha():
    """A pixel at luminance 90 with this_min=100, feather=20 should
    pass at α = (90 - 80) / 20 = 0.5."""
    img = _solid((90, 90, 90))   # luminance ≈ 90
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(this_min=100, this_min_feather=20),
    )
    assert abs(float(mask[0, 0]) - 0.5) < 0.05


def test_blend_if_this_max_feather_intermediate_alpha():
    img = _solid((210, 210, 210))   # luminance ~ 210
    mask = compute_blend_if_mask(
        img, None,
        BlendIf(this_max=200, this_max_feather=20),
    )
    # 220 - 210 = 10, 10/20 = 0.5.
    assert abs(float(mask[0, 0]) - 0.5) < 0.05


# ---------------------------------------------------------------------------
# Underlying layer
# ---------------------------------------------------------------------------


def test_blend_if_underlying_filter_with_dark_underneath():
    """Layer is fully visible, but the underlying composite is dark
    so the blend-if rule (underlying_min=100) hides every pixel."""
    layer = _solid((128, 128, 128))
    underlying = _solid((10, 10, 10))   # luminance ≈ 10
    mask = compute_blend_if_mask(
        layer, underlying,
        BlendIf(underlying_min=100),
    )
    np.testing.assert_array_equal(mask, np.zeros_like(mask))


def test_blend_if_underlying_passes_when_in_range():
    layer = _solid((128, 128, 128))
    underlying = _solid((150, 150, 150))   # luminance 150
    mask = compute_blend_if_mask(
        layer, underlying,
        BlendIf(underlying_min=100, underlying_max=200),
    )
    np.testing.assert_array_equal(mask, np.ones_like(mask))


def test_blend_if_combines_this_and_underlying():
    """Both gates active — alpha is the elementwise product."""
    layer = _solid((128, 128, 128))
    underlying = _solid((90, 90, 90))   # luminance ≈ 90
    mask = compute_blend_if_mask(
        layer, underlying,
        BlendIf(
            this_min=50, this_max=200,
            underlying_min=100, underlying_min_feather=20,
        ),
    )
    # this_alpha = 1 (128 in [50, 200]), und_alpha ≈ 0.5
    assert abs(float(mask[0, 0]) - 0.5) < 0.05


def test_blend_if_rejects_non_rgba_layer():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        compute_blend_if_mask(rgb, None, BlendIf())


def test_blend_if_rejects_underlying_shape_mismatch():
    layer = _solid((128, 128, 128), h=4, w=4)
    bad_underlying = _solid((100, 100, 100), h=8, w=8)
    with pytest.raises(ValueError, match="same"):
        compute_blend_if_mask(layer, bad_underlying, BlendIf())


# ---------------------------------------------------------------------------
# Integration with PaintDocument.composite
# ---------------------------------------------------------------------------


def test_composite_applies_blend_if():
    """A layer with blend_if set hides pixels outside the band."""
    doc = PaintDocument()
    base = _solid((255, 255, 255), h=4, w=4)
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (50, 50, 50)
    above.image[..., 3] = 255
    above.blend_if = BlendIf(this_min=100)   # hide dark layer
    doc.invalidate_composite()
    out = doc.composite()
    # The dark layer is gated off, so the white background shows through.
    assert tuple(out[0, 0, :3]) == (255, 255, 255)


def test_composite_blend_if_underlying_gate():
    doc = PaintDocument()
    base = _solid((30, 30, 30), h=4, w=4)   # dark underlying
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (200, 200, 200)
    above.image[..., 3] = 255
    above.blend_if = BlendIf(underlying_min=100)   # hide above when under is dark
    doc.invalidate_composite()
    out = doc.composite()
    # Underlying is too dark → above is gated → base shows through.
    assert tuple(out[0, 0, :3]) == (30, 30, 30)
