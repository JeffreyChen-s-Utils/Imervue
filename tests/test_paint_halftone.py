"""Tests for the halftone screentone engine."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.halftone import (
    DEFAULT_LPI,
    HALFTONE_LPI_MAX,
    HALFTONE_LPI_MIN,
    apply_halftone_to_alpha,
    lpi_to_cell_pixels,
    map_value_to_halftone,
    render_halftone_dots,
    rotate_tile,
    value_to_density,
)


# ---------------------------------------------------------------------------
# value_to_density
# ---------------------------------------------------------------------------


def test_value_to_density_inverts_input():
    """High value (light) → low density; low value (dark) → high density."""
    value = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
    density = value_to_density(value)
    assert density[0, 0] > density[0, 1]
    assert density[0, 1] > density[0, 2]


def test_value_to_density_clamps_extremes():
    value = np.array([[-1.0, 0.0, 1.0, 2.0]], dtype=np.float32)
    density = value_to_density(value)
    # Even at value=0 (full black) density caps below 1.0 so the
    # rendered tone never collapses to a flat fill.
    assert density.max() < 1.0
    # Pure white → density floor (also non-zero).
    assert density.min() > 0.0


def test_value_to_density_returns_float32():
    value = np.zeros((4, 4), dtype=np.float32)
    out = value_to_density(value)
    assert out.dtype == np.float32


def test_value_to_density_rejects_non_2d_input():
    with pytest.raises(ValueError):
        value_to_density(np.zeros((4, 4, 3), dtype=np.float32))


# ---------------------------------------------------------------------------
# lpi_to_cell_pixels
# ---------------------------------------------------------------------------


def test_lpi_to_cell_pixels_inverse_of_dpi_per_lpi():
    cell = lpi_to_cell_pixels(60, dpi=300)
    assert cell == 5


def test_lpi_to_cell_pixels_clamped_to_minimum_two():
    """Even an absurdly high LPI still returns a 2-pixel cell so the
    dot has somewhere to live."""
    cell = lpi_to_cell_pixels(10_000, dpi=300)
    assert cell >= 2


def test_lpi_to_cell_pixels_rejects_nonpositive():
    with pytest.raises(ValueError):
        lpi_to_cell_pixels(0)
    with pytest.raises(ValueError):
        lpi_to_cell_pixels(60, dpi=0)


def test_default_lpi_within_documented_range():
    assert HALFTONE_LPI_MIN <= DEFAULT_LPI <= HALFTONE_LPI_MAX


# ---------------------------------------------------------------------------
# render_halftone_dots
# ---------------------------------------------------------------------------


def test_render_halftone_returns_rgba_uint8():
    density = np.full((16, 16), 0.5, dtype=np.float32)
    out = render_halftone_dots(density, cell=4)
    assert out.shape == (16, 16, 4)
    assert out.dtype == np.uint8


def test_render_halftone_zero_density_is_empty():
    density = np.zeros((16, 16), dtype=np.float32)
    out = render_halftone_dots(density, cell=4)
    assert out[..., 3].max() == 0


def test_render_halftone_high_density_has_more_ink_than_low():
    low = render_halftone_dots(
        np.full((16, 16), 0.2, dtype=np.float32), cell=4,
    )
    high = render_halftone_dots(
        np.full((16, 16), 0.8, dtype=np.float32), cell=4,
    )
    assert high[..., 3].sum() > low[..., 3].sum()


def test_render_halftone_rejects_invalid_cell():
    density = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        render_halftone_dots(density, cell=1)


def test_render_halftone_rejects_non_2d_density():
    with pytest.raises(ValueError):
        render_halftone_dots(np.zeros((4, 4, 3), dtype=np.float32), cell=4)


# ---------------------------------------------------------------------------
# apply_halftone_to_alpha
# ---------------------------------------------------------------------------


def _alpha_layer(h: int, w: int, alpha: int) -> np.ndarray:
    layer = np.zeros((h, w, 4), dtype=np.uint8)
    layer[..., 3] = alpha
    return layer


def test_apply_halftone_to_alpha_returns_rgba_uint8():
    layer = _alpha_layer(32, 32, 128)
    out = apply_halftone_to_alpha(layer, lpi=60)
    assert out.shape == layer.shape
    assert out.dtype == np.uint8


def test_apply_halftone_to_alpha_does_not_mutate_input():
    layer = _alpha_layer(16, 16, 128)
    snapshot = layer.copy()
    apply_halftone_to_alpha(layer, lpi=60)
    assert np.array_equal(layer, snapshot)


def test_apply_halftone_to_alpha_higher_alpha_more_ink():
    light = apply_halftone_to_alpha(_alpha_layer(32, 32, 60), lpi=60)
    dark = apply_halftone_to_alpha(_alpha_layer(32, 32, 220), lpi=60)
    assert dark[..., 3].sum() > light[..., 3].sum()


def test_apply_halftone_to_alpha_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_halftone_to_alpha(bad)


# ---------------------------------------------------------------------------
# map_value_to_halftone
# ---------------------------------------------------------------------------


def test_map_value_to_halftone_uses_requested_color():
    value = np.full((32, 32), 0.5, dtype=np.float32)
    out = map_value_to_halftone(value, color=(255, 0, 0), lpi=60)
    # Every pixel in the output uses the requested colour for RGB —
    # the dots are red even though the alpha varies.
    assert (out[..., 0] == 255).all()
    assert (out[..., 1] == 0).all()
    assert (out[..., 2] == 0).all()


def test_map_value_to_halftone_alpha_varies_with_value():
    light = map_value_to_halftone(
        np.full((32, 32), 0.9, dtype=np.float32), lpi=60,
    )
    dark = map_value_to_halftone(
        np.full((32, 32), 0.1, dtype=np.float32), lpi=60,
    )
    assert dark[..., 3].sum() > light[..., 3].sum()


def test_map_value_to_halftone_rejects_invalid_color():
    value = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        map_value_to_halftone(value, color=(300, 0, 0))


# ---------------------------------------------------------------------------
# rotate_tile
# ---------------------------------------------------------------------------


def test_rotate_tile_zero_degrees_round_trips():
    tile = np.zeros((8, 8, 4), dtype=np.uint8)
    tile[2, 3] = (10, 20, 30, 255)
    out = rotate_tile(tile, angle_deg=0.0)
    assert np.array_equal(out, tile)


def test_rotate_tile_360_degrees_round_trips():
    tile = np.zeros((8, 8, 4), dtype=np.uint8)
    tile[2, 3] = (10, 20, 30, 255)
    out = rotate_tile(tile, angle_deg=360.0)
    assert np.array_equal(out, tile)


def test_rotate_tile_preserves_size():
    tile = np.zeros((16, 16, 4), dtype=np.uint8)
    out = rotate_tile(tile, angle_deg=30.0)
    assert out.shape == tile.shape


def test_rotate_tile_45_changes_a_solid_pattern():
    """A non-symmetric pattern rotated 45° must not equal the input
    (catch a no-op / wrong-axis bug)."""
    tile = np.zeros((9, 9, 4), dtype=np.uint8)
    tile[0, :] = (0, 0, 0, 255)   # top row only
    out = rotate_tile(tile, angle_deg=45.0)
    assert not np.array_equal(out, tile)


def test_rotate_tile_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        rotate_tile(bad, angle_deg=15.0)


# ---------------------------------------------------------------------------
# Round-trip: paint with grey → convert → still has the same overall ink
# ---------------------------------------------------------------------------


def test_halftone_conversion_preserves_overall_tone_strength():
    """A uniform 50%-alpha layer converted to halftone produces an
    output whose total ink is roughly proportional to the input
    coverage. This catches a wrong-direction density mapping."""
    layer = _alpha_layer(64, 64, 128)   # ~50% ink
    out = apply_halftone_to_alpha(layer, lpi=DEFAULT_LPI)
    # Total alpha across the output should be a meaningful fraction
    # of "all pixels fully on" — neither near zero nor near saturation.
    total = out[..., 3].sum()
    full = 64 * 64 * 255
    fraction = total / full
    assert 0.2 < fraction < 0.8


# ---------------------------------------------------------------------------
# ToneSettings + render_tone_layer
# ---------------------------------------------------------------------------


def test_tone_settings_defaults_pass_validation():
    from Imervue.paint.halftone import ToneSettings
    tone = ToneSettings()
    assert tone.lpi == DEFAULT_LPI
    assert tone.color == (0, 0, 0)


def test_tone_settings_rejects_lpi_below_min():
    from Imervue.paint.halftone import ToneSettings
    with pytest.raises(ValueError):
        ToneSettings(lpi=HALFTONE_LPI_MIN - 1)


def test_tone_settings_rejects_lpi_above_max():
    from Imervue.paint.halftone import ToneSettings
    with pytest.raises(ValueError):
        ToneSettings(lpi=HALFTONE_LPI_MAX + 1)


def test_tone_settings_rejects_non_positive_dpi():
    from Imervue.paint.halftone import ToneSettings
    with pytest.raises(ValueError):
        ToneSettings(dpi=0)


def test_tone_settings_rejects_bad_color_length():
    from Imervue.paint.halftone import ToneSettings
    with pytest.raises(ValueError):
        ToneSettings(color=(0, 0))   # type: ignore[arg-type]


def test_tone_settings_rejects_color_out_of_range():
    from Imervue.paint.halftone import ToneSettings
    with pytest.raises(ValueError):
        ToneSettings(color=(0, 0, 999))


def test_tone_settings_round_trips_via_to_from_dict():
    from Imervue.paint.halftone import ToneSettings
    original = ToneSettings(lpi=80, dpi=600, angle_deg=45.0, color=(10, 20, 30))
    rebuilt = ToneSettings.from_dict(original.to_dict())
    assert rebuilt == original


def test_tone_settings_from_dict_returns_none_for_garbage():
    from Imervue.paint.halftone import ToneSettings
    assert ToneSettings.from_dict(None) is None
    assert ToneSettings.from_dict({"lpi": "not-an-int"}) is None
    assert ToneSettings.from_dict({"color": [0, 0]}) is None


def test_render_tone_layer_paints_dots_in_dark_areas():
    from Imervue.paint.halftone import ToneSettings, render_tone_layer
    layer = np.zeros((32, 32, 4), dtype=np.uint8)
    layer[..., 3] = 255   # opaque
    layer[..., :3] = 0    # black → high density
    out = render_tone_layer(layer, ToneSettings(lpi=60))
    # Some pixels are inside dots, some are between them — the alpha
    # field is bimodal, with a non-trivial fraction inked.
    inked = (out[..., 3] > 0).mean()
    assert 0.2 < inked < 0.95


def test_render_tone_layer_uses_tone_color():
    from Imervue.paint.halftone import ToneSettings, render_tone_layer
    layer = np.zeros((32, 32, 4), dtype=np.uint8)
    layer[..., 3] = 255
    layer[..., :3] = 0
    out = render_tone_layer(
        layer, ToneSettings(lpi=60, color=(200, 30, 60)),
    )
    # Pick a pixel inside a dot — its RGB should be the tone colour,
    # not the original layer's grayscale.
    inside = out[out[..., 3] > 0]
    assert inside.size > 0
    assert (inside[:, 0] == 200).all()
    assert (inside[:, 1] == 30).all()
    assert (inside[:, 2] == 60).all()


def test_render_tone_layer_white_input_yields_almost_no_dots():
    """High-luma input (light grey paint) → near-empty halftone."""
    from Imervue.paint.halftone import ToneSettings, render_tone_layer
    layer = np.full((32, 32, 4), 255, dtype=np.uint8)
    out = render_tone_layer(layer, ToneSettings(lpi=60))
    # Density floor is ~5% so a tiny fraction of pixels still gets
    # inked, but not many.
    inked = (out[..., 3] > 0).mean()
    assert inked < 0.2


def test_render_tone_layer_rejects_non_rgba():
    from Imervue.paint.halftone import ToneSettings, render_tone_layer
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        render_tone_layer(bad, ToneSettings())


def test_render_tone_layer_angle_rotates_pattern():
    """A 45° rotation must produce a different dot mask vs 0°."""
    from Imervue.paint.halftone import ToneSettings, render_tone_layer
    layer = np.zeros((32, 32, 4), dtype=np.uint8)
    layer[..., 3] = 255
    layer[..., :3] = 80   # mid-grey
    a = render_tone_layer(layer, ToneSettings(lpi=60, angle_deg=0.0))
    b = render_tone_layer(layer, ToneSettings(lpi=60, angle_deg=45.0))
    assert not np.array_equal(a[..., 3], b[..., 3])
