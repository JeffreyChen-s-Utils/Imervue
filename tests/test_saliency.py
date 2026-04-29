"""Tests for the saliency-driven smart crop helper."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.saliency import (
    ASPECT_PRESETS,
    CropSuggestion,
    saliency_field,
    suggest_crops,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def _checker(h, w, square=4):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    yy, xx = np.indices((h, w))
    mask = ((xx // square) + (yy // square)) % 2 == 0
    arr[mask, 0] = 255
    arr[mask, 1] = 255
    arr[mask, 2] = 255
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# saliency_field
# ---------------------------------------------------------------------------


def test_saliency_field_shape_matches_input():
    arr = _solid(16, 24, (100, 100, 100))
    out = saliency_field(arr)
    assert out.shape == (16, 24)
    assert out.dtype == np.float32


def test_saliency_field_in_zero_one_range():
    arr = _checker(32, 32, square=4)
    field = saliency_field(arr)
    assert field.min() >= 0.0
    assert field.max() <= 1.0


def test_saliency_field_higher_for_textured_input():
    """Edge-rich input should have a higher mean saliency than a flat one."""
    flat = _solid(32, 32, (128, 128, 128))
    textured = _checker(32, 32, square=4)
    assert saliency_field(textured).mean() > saliency_field(flat).mean()


def test_saliency_field_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        saliency_field(arr)


# ---------------------------------------------------------------------------
# suggest_crops
# ---------------------------------------------------------------------------


def test_suggest_crops_returns_one_per_preset():
    arr = _checker(64, 64, square=4)
    out = suggest_crops(arr, presets=("free", "1:1", "16:9"))
    assert set(out.keys()) == {"free", "1:1", "16:9"}
    for suggestion in out.values():
        assert isinstance(suggestion, CropSuggestion)


def test_suggest_crops_free_preset_returns_full_frame():
    arr = _checker(64, 64, square=4)
    out = suggest_crops(arr, presets=("free",))
    free = out["free"]
    assert (free.x, free.y) == (0, 0)
    assert (free.w, free.h) == (64, 64)


def test_suggest_crops_aspect_ratios_match_preset():
    """Each non-free crop's w/h ratio should hit the preset within rounding."""
    arr = _checker(120, 200, square=8)
    out = suggest_crops(arr, presets=("1:1", "4:5", "16:9"))
    for preset, suggestion in out.items():
        target = ASPECT_PRESETS[preset]
        if target is None:
            continue
        actual = suggestion.w / suggestion.h
        # Allow 5% rounding slack — sizes are integer pixels
        assert abs(actual - target) / target < 0.06, (
            f"preset {preset}: ratio {actual:.3f} vs target {target:.3f}"
        )


def test_suggest_crops_stays_inside_image():
    arr = _checker(64, 96, square=4)
    out = suggest_crops(arr)
    h, w = arr.shape[:2]
    for suggestion in out.values():
        assert suggestion.x >= 0
        assert suggestion.y >= 0
        assert suggestion.x + suggestion.w <= w
        assert suggestion.y + suggestion.h <= h


def test_suggest_crops_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        suggest_crops(arr)


def test_suggest_crops_score_is_finite():
    arr = _checker(48, 48)
    for suggestion in suggest_crops(arr).values():
        assert np.isfinite(suggestion.score)


def test_suggest_crops_aspect_presets_include_known_ratios():
    """The public preset registry should expose the documented set."""
    expected = {"free", "1:1", "4:5", "3:2", "16:9"}
    assert expected.issubset(set(ASPECT_PRESETS.keys()))


def test_suggest_crops_offcentre_subject_pulls_anchor():
    """When the saliency mass is on one side, the picked rect leans toward it."""
    arr = _solid(80, 80, (10, 10, 10))
    # Paint a bright square on the left third to skew the saliency.
    arr[20:60, 5:30, :3] = 240
    out = suggest_crops(arr, presets=("1:1",))
    chosen = out["1:1"]
    centre_x = chosen.x + chosen.w / 2.0
    # Rect centre should fall to the left of the image centre
    assert centre_x < 40
