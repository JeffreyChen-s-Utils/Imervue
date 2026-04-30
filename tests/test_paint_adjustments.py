"""Tests for non-destructive adjustment layers."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.adjustments import (
    ADJUSTMENT_KINDS,
    Adjustment,
    apply_adjustment,
)
from Imervue.paint.document import PaintDocument


# ---------------------------------------------------------------------------
# Adjustment dataclass
# ---------------------------------------------------------------------------


def test_adjustment_kinds_set():
    # 13b extends this — assert the original three are still present.
    assert {"levels", "curves", "hsv"} <= set(ADJUSTMENT_KINDS)


def test_adjustment_construction_default_params():
    a = Adjustment(kind="levels")
    assert a.kind == "levels"
    assert isinstance(a.params, dict)


def test_adjustment_is_frozen():
    a = Adjustment(kind="levels")
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.kind = "hsv"  # type: ignore[misc]


def test_adjustment_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown"):
        Adjustment(kind="alien")


def test_adjustment_rejects_non_dict_params():
    with pytest.raises(ValueError, match="dict"):
        Adjustment(kind="levels", params="bad")  # type: ignore[arg-type]


def test_adjustment_round_trip_via_dict():
    a = Adjustment(kind="levels", params={"input_black": 20, "input_white": 230})
    rebuilt = Adjustment.from_dict(a.to_dict())
    assert rebuilt.kind == "levels"
    assert rebuilt.params["input_black"] == 20


def test_adjustment_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        Adjustment.from_dict("garbage")  # type: ignore[arg-type]


def test_adjustment_from_dict_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown"):
        Adjustment.from_dict({"kind": "alien"})


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------


def _solid_image(rgb: tuple[int, int, int], shape=(4, 4)):
    img = np.zeros((shape[0], shape[1], 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


def test_levels_identity_preserves_pixels():
    img = _solid_image((100, 50, 200))
    out = apply_adjustment(img, Adjustment(kind="levels"))
    np.testing.assert_array_equal(out, img)


def test_levels_increases_contrast_via_input_range():
    img = _solid_image((128, 128, 128))
    out = apply_adjustment(
        img, Adjustment(kind="levels", params={"input_black": 100, "input_white": 156}),
    )
    # 128 maps to ~(128-100)/56 = 0.5 → output 127. Allow ±2 for rounding.
    assert abs(int(out[0, 0, 0]) - 127) <= 2


def test_levels_compresses_output_range():
    img = _solid_image((255, 255, 255))
    out = apply_adjustment(
        img, Adjustment(kind="levels", params={
            "output_black": 50, "output_white": 200,
        }),
    )
    # Pure white maps to output_white = 200.
    assert int(out[0, 0, 0]) == 200


def test_levels_gamma_above_one_brightens_midtones():
    img = _solid_image((128, 128, 128))
    bright = apply_adjustment(img, Adjustment(kind="levels", params={"gamma": 2.0}))
    assert int(bright[0, 0, 0]) > 128


def test_levels_alpha_unchanged():
    img = _solid_image((100, 100, 100))
    img[..., 3] = 200
    out = apply_adjustment(
        img, Adjustment(kind="levels", params={"input_black": 50, "input_white": 200}),
    )
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Curves
# ---------------------------------------------------------------------------


def test_curves_identity_preserves_pixels():
    img = _solid_image((128, 64, 200))
    out = apply_adjustment(img, Adjustment(kind="curves"))
    np.testing.assert_array_equal(out, img)


def test_curves_inversion_via_negative_slope():
    img = _solid_image((10, 200, 50))
    out = apply_adjustment(
        img, Adjustment(kind="curves", params={"points": [[0, 255], [255, 0]]}),
    )
    # Inverted curve: 10 → 245, 200 → 55, 50 → 205. Allow ±2 rounding.
    assert abs(int(out[0, 0, 0]) - 245) <= 2
    assert abs(int(out[0, 0, 1]) - 55) <= 2
    assert abs(int(out[0, 0, 2]) - 205) <= 2


def test_curves_with_single_point_fallback_to_identity():
    img = _solid_image((100, 100, 100))
    out = apply_adjustment(
        img, Adjustment(kind="curves", params={"points": [[50, 200]]}),
    )
    np.testing.assert_array_equal(out, img)


def test_curves_lifts_shadows():
    img = _solid_image((30, 30, 30))
    out = apply_adjustment(
        img, Adjustment(kind="curves", params={
            "points": [[0, 30], [255, 255]],
        }),
    )
    # The point (0, 30) lifts every input >= 30, so 30 → ~54.
    assert int(out[0, 0, 0]) > 30


# ---------------------------------------------------------------------------
# HSV
# ---------------------------------------------------------------------------


def test_hsv_identity_preserves_pixels():
    img = _solid_image((128, 64, 200))
    out = apply_adjustment(img, Adjustment(kind="hsv"))
    # Identity round-trips through float32 HSV — allow ±1 rounding.
    np.testing.assert_allclose(out[..., :3], img[..., :3], atol=1)


def test_hsv_180_degree_hue_shift_inverts_red_to_cyan():
    img = _solid_image((255, 0, 0))   # pure red
    out = apply_adjustment(
        img, Adjustment(kind="hsv", params={"hue_shift_deg": 180.0}),
    )
    # Red rotated 180° → cyan: R≈0, G≈255, B≈255.
    assert int(out[0, 0, 0]) <= 5
    assert int(out[0, 0, 1]) >= 250
    assert int(out[0, 0, 2]) >= 250


def test_hsv_zero_saturation_yields_grayscale():
    img = _solid_image((200, 100, 50))
    out = apply_adjustment(
        img, Adjustment(kind="hsv", params={"saturation": 0.0}),
    )
    # Equal channels (within rounding) when saturation = 0.
    r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
    assert abs(r - g) <= 1
    assert abs(g - b) <= 1


def test_hsv_lightness_zero_yields_black():
    img = _solid_image((200, 100, 50))
    out = apply_adjustment(
        img, Adjustment(kind="hsv", params={"lightness": 0.0}),
    )
    assert (out[..., :3] == 0).all()


def test_hsv_alpha_unchanged():
    img = _solid_image((255, 0, 0))
    img[..., 3] = 200
    out = apply_adjustment(
        img, Adjustment(kind="hsv", params={"hue_shift_deg": 90.0}),
    )
    assert (out[..., 3] == 200).all()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_apply_adjustment_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        apply_adjustment(rgb, Adjustment(kind="levels"))


# ---------------------------------------------------------------------------
# PaintDocument integration
# ---------------------------------------------------------------------------


@pytest.fixture
def doc_with_solid_layer():
    doc = PaintDocument()
    base = np.zeros((4, 4, 4), dtype=np.uint8)
    base[..., :3] = (100, 100, 100)
    base[..., 3] = 255
    doc.load_image(base)
    return doc


def test_add_adjustment_layer_appears_in_stack(doc_with_solid_layer):
    doc = doc_with_solid_layer
    doc.add_adjustment_layer(
        Adjustment(kind="levels", params={"gamma": 2.0}),
    )
    assert doc.layer_count == 2
    assert doc.layers()[1].adjustment is not None


def test_adjustment_layer_modifies_composite(doc_with_solid_layer):
    doc = doc_with_solid_layer
    doc.add_adjustment_layer(
        Adjustment(kind="hsv", params={"lightness": 0.0}),
    )
    out = doc.composite()
    # Lightness 0 → everything beneath becomes black.
    assert (out[..., :3] == 0).all()


def test_adjustment_layer_skipped_when_invisible(doc_with_solid_layer):
    doc = doc_with_solid_layer
    layer = doc.add_adjustment_layer(
        Adjustment(kind="hsv", params={"lightness": 0.0}),
    )
    layer.visible = False
    doc.invalidate_composite()
    out = doc.composite()
    # Layer hidden → black-out is bypassed; original 100 RGB shows.
    assert int(out[0, 0, 0]) == 100


def test_adjustment_layer_below_normal_layer_still_modifies_only_below(doc_with_solid_layer):
    """A layer composited ABOVE the adjustment must not be re-adjusted."""
    doc = doc_with_solid_layer
    # Adjustment above the background.
    doc.add_adjustment_layer(
        Adjustment(kind="hsv", params={"lightness": 0.0}),
    )
    # Then a solid white layer above the adjustment.
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (200, 200, 200)
    above.image[..., 3] = 255
    doc.invalidate_composite()
    out = doc.composite()
    # Above paints over the blacked-out background — final pixel is 200.
    assert int(out[0, 0, 0]) == 200


def test_adjustment_layer_partial_opacity_blends(doc_with_solid_layer):
    doc = doc_with_solid_layer
    layer = doc.add_adjustment_layer(
        Adjustment(kind="hsv", params={"lightness": 0.0}),
    )
    layer.opacity = 0.5
    doc.invalidate_composite()
    out = doc.composite()
    # Half-strength black-out: 100 mid-blends to ~50.
    assert abs(int(out[0, 0, 0]) - 50) <= 2


def test_adjustment_layer_persists_via_document_io(tmp_path):
    from Imervue.paint.document_io import load_document, save_document
    doc = PaintDocument()
    base = np.zeros((4, 4, 4), dtype=np.uint8)
    base[..., :3] = (200, 100, 50)
    base[..., 3] = 255
    doc.load_image(base)
    doc.add_adjustment_layer(
        Adjustment(kind="curves", params={"points": [[0, 0], [128, 200], [255, 255]]}),
    )
    path = tmp_path / "with_adj.imervue"
    save_document(doc, path)
    loaded = load_document(path)
    adj_layer = loaded.layers()[1]
    assert adj_layer.adjustment is not None
    assert adj_layer.adjustment.kind == "curves"
    assert adj_layer.adjustment.params["points"] == [[0, 0], [128, 200], [255, 255]]


def test_add_adjustment_layer_to_empty_document_raises():
    doc = PaintDocument()
    with pytest.raises(RuntimeError, match="empty"):
        doc.add_adjustment_layer(Adjustment(kind="levels"))
