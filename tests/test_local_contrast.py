"""Tests for clarity / texture local-contrast adjustments."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.local_contrast import apply_clarity, apply_texture


def _edge_rgba(h=32, w=32, left=100, right=140):
    rgb = np.empty((h, w, 3), dtype=np.uint8)
    rgb[:, : w // 2] = left
    rgb[:, w // 2 :] = right
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _flat_rgba(value=120, h=16, w=16):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_clarity_zero_is_identity():
    img = _edge_rgba()
    assert np.array_equal(apply_clarity(img, 0.0), img)


def test_texture_zero_is_identity():
    img = _edge_rgba()
    assert np.array_equal(apply_texture(img, 0.0), img)


def test_clarity_preserves_shape_dtype_alpha():
    img = _edge_rgba()
    out = apply_clarity(img, 0.5)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert np.all(out[..., 3] == 255)


def test_clarity_boosts_edge_contrast():
    img = _edge_rgba()
    out = apply_clarity(img, 1.0)
    in_rgb, out_rgb = img[..., :3], out[..., :3]
    # Unsharp overshoot brightens the bright side and darkens the dark side.
    assert out_rgb.max() > in_rgb.max()
    assert out_rgb.min() < in_rgb.min()


def test_negative_clarity_changes_image():
    img = _edge_rgba()
    out = apply_clarity(img, -1.0)
    assert not np.array_equal(out, img)


def test_flat_image_unchanged():
    img = _flat_rgba()
    # No local detail to amplify → both operators are no-ops on a flat field.
    assert np.array_equal(apply_clarity(img, 1.0), img)
    assert np.array_equal(apply_texture(img, 1.0), img)


def test_texture_changes_edge():
    img = _edge_rgba()
    assert not np.array_equal(apply_texture(img, 1.0), img)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        apply_clarity(np.zeros((8, 8), dtype=np.uint8), 1.0)
