"""Tests for procedural material generators + default catalog wiring."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.material_library import (
    MATERIAL_CATEGORIES,
    MaterialEntry,
    default_material_index,
)
from Imervue.paint.material_procedural import (
    DEFAULT_PROCEDURAL_CATALOG,
    DEFAULT_TILE_SIZE,
    checker_pattern,
    dot_tone,
    gradient_tone,
    line_tone,
    paper_noise,
    tile_to_canvas,
)


# ---------------------------------------------------------------------------
# Generators — shape + dtype + content sanity
# ---------------------------------------------------------------------------


def test_dot_tone_returns_rgba_uint8_of_requested_size():
    tile = dot_tone(size=64, cell=8, coverage=0.4)
    assert tile.shape == (64, 64, 4)
    assert tile.dtype == np.uint8


def test_dot_tone_zero_coverage_is_fully_transparent():
    tile = dot_tone(size=32, cell=8, coverage=0.0)
    assert np.all(tile[..., 3] == 0)


def test_dot_tone_full_coverage_has_visible_dots():
    tile = dot_tone(size=32, cell=8, coverage=1.0)
    # Some pixels must be opaque black after a full-coverage call.
    opaque = tile[..., 3] == 255
    assert opaque.any()


def test_dot_tone_rejects_nonpositive_size():
    with pytest.raises(ValueError):
        dot_tone(size=0, cell=4)
    with pytest.raises(ValueError):
        dot_tone(size=32, cell=0)


def test_line_tone_shape_and_dtype():
    tile = line_tone(size=40, spacing=5, angle_deg=30.0, thickness=2)
    assert tile.shape == (40, 40, 4)
    assert tile.dtype == np.uint8


def test_line_tone_horizontal_lines_appear():
    tile = line_tone(size=20, spacing=4, angle_deg=0.0, thickness=1)
    # Horizontal lines → at least one full row of opaque pixels.
    row_alpha = tile[..., 3].max(axis=1)
    assert (row_alpha == 255).any()


def test_line_tone_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        line_tone(size=0, spacing=4)
    with pytest.raises(ValueError):
        line_tone(size=32, spacing=-1)
    with pytest.raises(ValueError):
        line_tone(size=32, spacing=4, thickness=0)


def test_gradient_tone_vertical_alpha_is_monotonic_in_y():
    tile = gradient_tone(size=16, direction="vertical")
    column_means = tile[..., 3].mean(axis=1)
    assert np.all(np.diff(column_means) >= 0)


def test_gradient_tone_horizontal_alpha_is_monotonic_in_x():
    tile = gradient_tone(size=16, direction="horizontal")
    row_means = tile[..., 3].mean(axis=0)
    assert np.all(np.diff(row_means) >= 0)


def test_gradient_tone_rejects_unknown_direction():
    with pytest.raises(ValueError):
        gradient_tone(size=8, direction="diagonal")


def test_paper_noise_is_seeded_deterministically():
    a = paper_noise(size=32, intensity=0.15, seed=42)
    b = paper_noise(size=32, intensity=0.15, seed=42)
    assert np.array_equal(a, b)


def test_paper_noise_different_seeds_differ():
    a = paper_noise(size=32, intensity=0.15, seed=1)
    b = paper_noise(size=32, intensity=0.15, seed=2)
    assert not np.array_equal(a, b)


def test_paper_noise_zero_intensity_is_uniform_grey():
    tile = paper_noise(size=16, intensity=0.0, seed=0)
    # Every R,G,B sample equal across the tile.
    assert np.all(tile[..., 0] == tile[0, 0, 0])
    assert np.all(tile[..., 3] == 255)


def test_paper_noise_clamps_intensity():
    """An intensity above 1.0 is silently clamped so a careless caller
    never trips the std-dev formula into producing absurd noise."""
    tile = paper_noise(size=8, intensity=10.0, seed=0)
    # Result still in valid uint8 range — no overflow.
    assert tile.dtype == np.uint8
    assert tile[..., 3].max() == 255


def test_checker_pattern_alternates_two_tones():
    tile = checker_pattern(size=32, cell=8)
    # Top-left cell vs the cell to its right must differ.
    top_left = tuple(tile[0, 0])
    one_right = tuple(tile[0, 8])
    assert top_left != one_right


def test_checker_pattern_rejects_nonpositive_cell():
    with pytest.raises(ValueError):
        checker_pattern(size=16, cell=0)


# ---------------------------------------------------------------------------
# tile_to_canvas
# ---------------------------------------------------------------------------


def test_tile_to_canvas_repeats_to_target_shape():
    tile = checker_pattern(size=8, cell=2)
    out = tile_to_canvas(tile, (24, 32))
    assert out.shape == (24, 32, 4)
    # Tiling preserves the original pattern at the origin.
    assert np.array_equal(out[:8, :8], tile)


def test_tile_to_canvas_returns_input_when_already_correct_size():
    tile = checker_pattern(size=16, cell=4)
    out = tile_to_canvas(tile, (16, 16))
    assert out is tile  # no copy when shapes already match


def test_tile_to_canvas_crops_when_target_not_a_multiple():
    tile = dot_tone(size=10, cell=2, coverage=0.5)
    out = tile_to_canvas(tile, (15, 17))
    assert out.shape == (15, 17, 4)


def test_tile_to_canvas_rejects_non_rgba_input():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        tile_to_canvas(bad, (8, 8))


def test_tile_to_canvas_rejects_zero_target_dim():
    tile = dot_tone(size=4, cell=2)
    with pytest.raises(ValueError):
        tile_to_canvas(tile, (0, 4))


# ---------------------------------------------------------------------------
# Default catalog + index integration
# ---------------------------------------------------------------------------


def test_catalog_is_non_empty():
    assert len(DEFAULT_PROCEDURAL_CATALOG) > 0


def test_every_catalog_entry_uses_known_category():
    for _name, category, _tags, _provider in DEFAULT_PROCEDURAL_CATALOG:
        assert category in MATERIAL_CATEGORIES


def test_every_catalog_provider_returns_valid_rgba_tile():
    for name, _category, _tags, provider in DEFAULT_PROCEDURAL_CATALOG:
        tile = provider()
        assert tile.ndim == 3, f"{name}: bad ndim"
        assert tile.shape[2] == 4, f"{name}: not RGBA"
        assert tile.dtype == np.uint8, f"{name}: not uint8"


def test_default_index_lists_every_catalog_entry():
    index = default_material_index()
    assert len(index) == len(DEFAULT_PROCEDURAL_CATALOG)


def test_default_index_entries_are_procedural():
    index = default_material_index()
    for entry in index.entries:
        assert entry.is_procedural()
        assert entry.provider is not None


def test_default_index_categories_match_catalog():
    index = default_material_index()
    cats = set(index.categories())
    catalog_cats = {c for _n, c, _t, _p in DEFAULT_PROCEDURAL_CATALOG}
    assert cats == catalog_cats


def test_default_index_filter_by_tone_category():
    index = default_material_index()
    tone_entries = index.filter(category="tone")
    assert len(tone_entries) > 0
    assert all(e.category == "tone" for e in tone_entries)


def test_default_index_filter_by_search_query():
    index = default_material_index()
    # "dot" tag appears on every dot tone entry.
    matches = index.filter(query="dot")
    assert len(matches) >= 1
    for entry in matches:
        haystack = " ".join((entry.name, *entry.tags)).lower()
        assert "dot" in haystack


# ---------------------------------------------------------------------------
# MaterialEntry — provider plumbing
# ---------------------------------------------------------------------------


def test_path_entry_is_not_procedural(tmp_path):
    e = MaterialEntry(name="x", path=tmp_path / "x.png")
    assert not e.is_procedural()
    assert e.render() is None


def test_provider_entry_renders_via_callable():
    sentinel = np.zeros((4, 4, 4), dtype=np.uint8)
    sentinel[..., 3] = 255

    def provider():
        return sentinel

    e = MaterialEntry(
        name="proc", path="procedural://proc", category="texture",
        provider=provider,
    )
    assert e.is_procedural()
    out = e.render()
    assert out is sentinel


def test_to_dict_drops_provider_field():
    """Procedural entries must not crash JSON serialisation; the
    provider is simply omitted (callables are not JSON-friendly)."""
    e = MaterialEntry(
        name="proc", path="procedural://proc", category="tone",
        provider=lambda: np.zeros((2, 2, 4), dtype=np.uint8),
    )
    raw = e.to_dict()
    assert "provider" not in raw
    assert raw["name"] == "proc"
    assert raw["category"] == "tone"


def test_default_tile_size_is_reasonable():
    """A safety net so a casual edit to DEFAULT_TILE_SIZE that breaks
    the dock thumbnail layout (>256 px) is caught early."""
    assert 16 <= DEFAULT_TILE_SIZE <= 256
