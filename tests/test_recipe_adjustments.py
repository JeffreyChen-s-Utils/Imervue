"""Tests for the advanced develop slider math in recipe_adjustments."""
from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def adj():
    from Imervue.image import recipe_adjustments
    return recipe_adjustments


@pytest.fixture
def gray_rgba() -> np.ndarray:
    """Mid-grey RGBA image (128,128,128,255) of 16x16."""
    arr = np.full((16, 16, 4), 128, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


@pytest.fixture
def gradient_rgba() -> np.ndarray:
    """Vertical gradient from dark (top) to bright (bottom)."""
    arr = np.zeros((32, 16, 4), dtype=np.uint8)
    for y in range(32):
        arr[y, :, :3] = int(y * 255 / 31)
    arr[..., 3] = 255
    return arr


class TestWhiteBalance:
    def test_zero_is_identity(self, adj, gray_rgba):
        out = adj.apply_white_balance(gray_rgba, 0.0, 0.0)
        assert np.array_equal(out, gray_rgba)

    def test_positive_temperature_warms(self, adj, gray_rgba):
        out = adj.apply_white_balance(gray_rgba, 0.5, 0.0)
        # Red channel up, blue channel down
        assert out[0, 0, 0] > gray_rgba[0, 0, 0]
        assert out[0, 0, 2] < gray_rgba[0, 0, 2]

    def test_negative_temperature_cools(self, adj, gray_rgba):
        out = adj.apply_white_balance(gray_rgba, -0.5, 0.0)
        assert out[0, 0, 0] < gray_rgba[0, 0, 0]
        assert out[0, 0, 2] > gray_rgba[0, 0, 2]

    def test_alpha_preserved(self, adj, gray_rgba):
        out = adj.apply_white_balance(gray_rgba, 0.5, 0.2)
        assert np.array_equal(out[..., 3], gray_rgba[..., 3])

    def test_no_mutation_of_input(self, adj, gray_rgba):
        snapshot = gray_rgba.copy()
        adj.apply_white_balance(gray_rgba, 0.5, 0.2)
        assert np.array_equal(gray_rgba, snapshot)


class TestHighlightsShadows:
    def test_zero_is_identity(self, adj, gradient_rgba):
        out = adj.apply_highlights_shadows(gradient_rgba, 0.0, 0.0)
        assert np.array_equal(out, gradient_rgba)

    def test_positive_shadows_lifts_dark(self, adj, gradient_rgba):
        out = adj.apply_highlights_shadows(gradient_rgba, 0.0, 0.8)
        # Dark rows (near top) should brighten
        assert out[2, 0, 0] >= gradient_rgba[2, 0, 0]

    def test_negative_highlights_recovers(self, adj, gradient_rgba):
        out = adj.apply_highlights_shadows(gradient_rgba, -0.8, 0.0)
        # Bright rows (near bottom) should darken
        assert out[30, 0, 0] <= gradient_rgba[30, 0, 0]

    def test_no_mutation_of_input(self, adj, gradient_rgba):
        snapshot = gradient_rgba.copy()
        adj.apply_highlights_shadows(gradient_rgba, -0.5, 0.5)
        assert np.array_equal(gradient_rgba, snapshot)


class TestWhitesBlacks:
    def test_zero_is_identity(self, adj, gradient_rgba):
        out = adj.apply_whites_blacks(gradient_rgba, 0.0, 0.0)
        assert np.array_equal(out, gradient_rgba)

    def test_clip_returns_valid_byte_range(self, adj, gradient_rgba):
        out = adj.apply_whites_blacks(gradient_rgba, 1.0, -1.0)
        assert out.dtype == np.uint8
        assert out[..., :3].max() <= 255
        assert out[..., :3].min() >= 0

    def test_alpha_preserved(self, adj, gradient_rgba):
        out = adj.apply_whites_blacks(gradient_rgba, 0.5, -0.5)
        assert np.array_equal(out[..., 3], gradient_rgba[..., 3])


class TestVibrance:
    def test_zero_is_identity(self, adj, gray_rgba):
        out = adj.apply_vibrance(gray_rgba, 0.0)
        assert np.array_equal(out, gray_rgba)

    def test_positive_vibrance_boosts_unsaturated(self, adj):
        # Slightly red pixel — low saturation so vibrance should hit it hardest
        arr = np.full((8, 8, 4), 128, dtype=np.uint8)
        arr[..., 0] = 160
        arr[..., 3] = 255
        out = adj.apply_vibrance(arr, 0.8)
        # Red should pull further from gray, green/blue should drop
        assert out[0, 0, 0] > arr[0, 0, 0]
        assert out[0, 0, 1] < arr[0, 0, 1]

    def test_alpha_preserved(self, adj, gray_rgba):
        out = adj.apply_vibrance(gray_rgba, 0.5)
        assert np.array_equal(out[..., 3], gray_rgba[..., 3])

    def test_no_mutation_of_input(self, adj):
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[..., 0] = 180
        arr[..., 3] = 255
        snapshot = arr.copy()
        adj.apply_vibrance(arr, 0.7)
        assert np.array_equal(arr, snapshot)


class TestIsZero:
    def test_exact_zero(self, adj):
        assert adj.is_zero(0.0) is True

    def test_within_tolerance(self, adj):
        assert adj.is_zero(1e-9) is True

    def test_outside_tolerance(self, adj):
        assert adj.is_zero(0.01) is False


class TestRecipePipelineIntegration:
    """End-to-end tests that the new adjustments round-trip through Recipe.apply."""

    def test_recipe_with_advanced_fields_applies(self, gray_rgba):
        from Imervue.image.recipe import Recipe
        recipe = Recipe(
            temperature=0.2,
            tint=-0.1,
            highlights=-0.3,
            shadows=0.3,
            whites=0.1,
            blacks=-0.1,
            vibrance=0.4,
        )
        out = recipe.apply(gray_rgba)
        assert out.shape == gray_rgba.shape
        assert out.dtype == np.uint8
        # Non-identity recipe must produce a different image
        assert not np.array_equal(out, gray_rgba)

    def test_identity_recipe_returns_input(self, gray_rgba):
        from Imervue.image.recipe import Recipe
        recipe = Recipe()
        out = recipe.apply(gray_rgba)
        assert np.array_equal(out, gray_rgba)

    def test_recipe_round_trip_preserves_new_fields(self):
        from Imervue.image.recipe import Recipe
        original = Recipe(
            temperature=0.25, tint=-0.4, highlights=-0.2, shadows=0.6,
            whites=0.15, blacks=-0.35, vibrance=0.5,
        )
        restored = Recipe.from_dict(original.to_dict())
        assert restored.temperature == pytest.approx(0.25)
        assert restored.tint == pytest.approx(-0.4)
        assert restored.highlights == pytest.approx(-0.2)
        assert restored.shadows == pytest.approx(0.6)
        assert restored.whites == pytest.approx(0.15)
        assert restored.blacks == pytest.approx(-0.35)
        assert restored.vibrance == pytest.approx(0.5)

    def test_is_identity_detects_advanced_slider(self):
        from Imervue.image.recipe import Recipe
        assert Recipe().is_identity() is True
        assert Recipe(temperature=0.1).is_identity() is False
        assert Recipe(vibrance=0.1).is_identity() is False

    def test_recipe_hash_changes_with_advanced_field(self):
        from Imervue.image.recipe import Recipe
        base = Recipe(exposure=0.1)
        warmed = Recipe(exposure=0.1, temperature=0.3)
        assert base.recipe_hash() != warmed.recipe_hash()
