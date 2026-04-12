"""Tests for Imervue.image.recipe."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.recipe import Recipe, file_identity, clear_identity_cache


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _checkerboard(h: int, w: int) -> np.ndarray:
    """Simple HxWx4 RGBA test image with a recognisable pattern."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[::2, ::2] = (255, 0, 0, 255)
    arr[1::2, 1::2] = (0, 255, 0, 255)
    arr[::2, 1::2] = (0, 0, 255, 255)
    arr[1::2, ::2] = (255, 255, 0, 255)
    return arr


# ======================================================================
# Identity / normalize
# ======================================================================

class TestRecipeIdentity:
    def test_default_is_identity(self):
        r = Recipe()
        assert r.is_identity()

    def test_rotate_not_identity(self):
        assert not Recipe(rotate_steps=1).is_identity()

    def test_rotate_4_is_identity_after_normalize(self):
        r = Recipe(rotate_steps=4).normalized()
        assert r.rotate_steps == 0
        assert r.is_identity()

    def test_zero_size_crop_dropped_by_normalize(self):
        r = Recipe(crop=(0, 0, 0, 10)).normalized()
        assert r.crop is None
        assert r.is_identity()

    def test_float_zero_is_identity(self):
        assert Recipe(brightness=0.0, contrast=0.0, saturation=0.0).is_identity()

    def test_any_nonzero_breaks_identity(self):
        for kwargs in [
            {"brightness": 0.1},
            {"contrast": -0.1},
            {"saturation": 0.5},
            {"exposure": 0.5},
            {"flip_h": True},
            {"flip_v": True},
            {"crop": (0, 0, 5, 5)},
        ]:
            assert not Recipe(**kwargs).is_identity(), kwargs


# ======================================================================
# Serialization
# ======================================================================

class TestRecipeSerialization:
    def test_round_trip_identity(self):
        r = Recipe()
        d = r.to_dict()
        r2 = Recipe.from_dict(d)
        assert r2.is_identity()

    def test_round_trip_full(self):
        r = Recipe(
            rotate_steps=1,
            flip_h=True,
            flip_v=False,
            crop=(10, 20, 100, 200),
            brightness=0.3,
            contrast=-0.2,
            saturation=0.5,
            exposure=0.4,
            extra={"panel_version": 2},
        )
        r2 = Recipe.from_dict(r.to_dict())
        assert r2.rotate_steps == 1
        assert r2.flip_h is True
        assert r2.crop == (10, 20, 100, 200)
        assert r2.brightness == pytest.approx(0.3)
        assert r2.extra == {"panel_version": 2}

    def test_crop_list_roundtrip(self):
        # to_dict() emits list for JSON compatibility; from_dict() must rebuild tuple
        d = {"crop": [1, 2, 3, 4]}
        r = Recipe.from_dict(d)
        assert r.crop == (1, 2, 3, 4)

    def test_unknown_fields_stashed_in_extra(self):
        d = {"future_field": "hello", "brightness": 0.1}
        r = Recipe.from_dict(d)
        assert r.brightness == pytest.approx(0.1)
        assert r.extra == {"future_field": "hello"}

    def test_round_trip_preserves_unknown_fields(self):
        d = {"brightness": 0.1, "future_field": "hello"}
        r = Recipe.from_dict(d)
        out = r.to_dict()
        assert out["extra"] == {"future_field": "hello"}


# ======================================================================
# Hashing
# ======================================================================

class TestRecipeHash:
    def test_identity_hashes_to_empty_string(self):
        assert Recipe().recipe_hash() == ""

    def test_hash_is_stable(self):
        r1 = Recipe(brightness=0.5)
        r2 = Recipe(brightness=0.5)
        assert r1.recipe_hash() == r2.recipe_hash()

    def test_different_recipes_hash_differently(self):
        assert Recipe(brightness=0.5).recipe_hash() != Recipe(brightness=0.6).recipe_hash()

    def test_hash_length_stable(self):
        assert len(Recipe(brightness=0.5).recipe_hash()) == 16

    def test_extra_field_doesnt_break_hash(self):
        r = Recipe(brightness=0.1, extra={"x": 1})
        assert len(r.recipe_hash()) == 16


# ======================================================================
# Apply — pixel-level transforms
# ======================================================================

class TestRecipeApplyGeometry:
    def test_identity_returns_input(self):
        arr = _checkerboard(8, 8)
        out = Recipe().apply(arr)
        assert out is arr  # short-circuit: no copy needed

    def test_rotate_90_cw_swaps_dimensions(self):
        arr = _checkerboard(6, 10)
        out = Recipe(rotate_steps=1).apply(arr)
        assert out.shape == (10, 6, 4)

    def test_rotate_180_preserves_shape(self):
        arr = _checkerboard(6, 10)
        out = Recipe(rotate_steps=2).apply(arr)
        assert out.shape == (6, 10, 4)

    def test_rotate_90_cw_then_ccw_roundtrip(self):
        arr = _checkerboard(6, 10)
        once = Recipe(rotate_steps=1).apply(arr)
        back = Recipe(rotate_steps=3).apply(once)
        np.testing.assert_array_equal(back, arr)

    def test_flip_h(self):
        arr = _checkerboard(4, 6)
        out = Recipe(flip_h=True).apply(arr)
        np.testing.assert_array_equal(out, arr[:, ::-1])

    def test_flip_v(self):
        arr = _checkerboard(4, 6)
        out = Recipe(flip_v=True).apply(arr)
        np.testing.assert_array_equal(out, arr[::-1, :])

    def test_crop_in_bounds(self):
        arr = _checkerboard(10, 10)
        out = Recipe(crop=(2, 3, 4, 5)).apply(arr)
        assert out.shape == (5, 4, 4)
        np.testing.assert_array_equal(out, arr[3:8, 2:6])

    def test_crop_clamped_to_image_bounds(self):
        arr = _checkerboard(10, 10)
        # crop overflows — should clamp, not crash
        out = Recipe(crop=(5, 5, 100, 100)).apply(arr)
        assert out.shape == (5, 5, 4)

    def test_crop_entirely_outside_returns_input(self):
        # Degenerate crop — falls back to unclipped array to avoid empty tensor.
        arr = _checkerboard(10, 10)
        out = Recipe(crop=(100, 100, 5, 5)).apply(arr)
        assert out.shape == (10, 10, 4)

    def test_output_dtype_is_uint8(self):
        arr = _checkerboard(4, 4)
        out = Recipe(rotate_steps=1, flip_h=True).apply(arr)
        assert out.dtype == np.uint8


class TestRecipeApplyColor:
    def test_brightness_up_increases_values(self):
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        out = Recipe(brightness=0.5).apply(arr)
        # PIL Brightness(1.5) scales RGB ~150
        assert out[0, 0, 0] > 100

    def test_brightness_down_decreases_values(self):
        arr = np.full((4, 4, 4), 200, dtype=np.uint8)
        arr[..., 3] = 255
        out = Recipe(brightness=-0.5).apply(arr)
        assert out[0, 0, 0] < 200

    def test_alpha_preserved_across_color_ops(self):
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[..., 3] = 128
        out = Recipe(brightness=0.3, contrast=0.3, saturation=0.3).apply(arr)
        # Alpha channel shouldn't be touched by brightness/contrast/saturation
        assert np.all(out[..., 3] == 128)

    def test_exposure_doubles_mid_gray_at_one_stop(self):
        arr = np.full((4, 4, 4), 64, dtype=np.uint8)
        arr[..., 3] = 255
        out = Recipe(exposure=1.0).apply(arr)
        assert out[0, 0, 0] == 128

    def test_exposure_clips_to_255(self):
        arr = np.full((4, 4, 4), 200, dtype=np.uint8)
        arr[..., 3] = 255
        out = Recipe(exposure=2.0).apply(arr)
        assert out[0, 0, 0] == 255

    def test_zero_size_crop_bounds_short_circuit(self):
        arr = _checkerboard(10, 10)
        r = Recipe(crop=(0, 0, 0, 10))  # invalid — zero width
        out = r.apply(arr)
        assert out.shape == (10, 10, 4)  # normalized drops crop -> identity


class TestRecipeApplyValidation:
    def test_rejects_wrong_shape(self):
        arr = np.zeros((4, 4), dtype=np.uint8)  # grayscale
        with pytest.raises(ValueError):
            Recipe(brightness=0.1).apply(arr)

    def test_rejects_rgb_only(self):
        arr = np.zeros((4, 4, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            Recipe(brightness=0.1).apply(arr)

    def test_converts_non_uint8_to_uint8(self):
        arr = np.zeros((4, 4, 4), dtype=np.uint16)
        out = Recipe(brightness=0.1).apply(arr)
        assert out.dtype == np.uint8


# ======================================================================
# file_identity
# ======================================================================

class TestFileIdentity:
    def test_returns_empty_for_missing_path(self, tmp_path):
        assert file_identity(tmp_path / "does_not_exist.png") == ""

    def test_stable_across_calls(self, tmp_path):
        p = tmp_path / "a.bin"
        p.write_bytes(b"hello world" * 100)
        clear_identity_cache()
        id1 = file_identity(p)
        id2 = file_identity(p)
        assert id1 == id2
        assert len(id1) == 32

    def test_changes_when_content_changes(self, tmp_path):
        p = tmp_path / "a.bin"
        p.write_bytes(b"one")
        clear_identity_cache()
        id1 = file_identity(p)
        p.write_bytes(b"two")
        clear_identity_cache()
        id2 = file_identity(p)
        assert id1 != id2

    def test_differs_on_size_even_if_head_matches(self, tmp_path):
        p1 = tmp_path / "short.bin"
        p2 = tmp_path / "long.bin"
        common = b"same header bytes " * 10
        p1.write_bytes(common)
        p2.write_bytes(common + b"extra")
        clear_identity_cache()
        assert file_identity(p1) != file_identity(p2)

    def test_cache_hit_returns_same_value(self, tmp_path):
        p = tmp_path / "a.bin"
        p.write_bytes(b"cached")
        clear_identity_cache()
        id1 = file_identity(p)
        # Second call hits the in-process cache
        id2 = file_identity(p)
        assert id1 == id2
