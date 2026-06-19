"""Tests for EXIF orientation transforms."""
from __future__ import annotations

import numpy as np

from Imervue.image.orientation import transform_for_orientation


def _asymmetric(h=2, w=3):
    return np.arange(h * w * 3, dtype=np.uint8).reshape(h, w, 3)


def test_identity():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 1), img)


def test_mirror_horizontal():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 2), img[:, ::-1])


def test_rotate_180():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 3), img[::-1, ::-1])


def test_rotate_90_cw_changes_dimensions():
    img = _asymmetric(2, 3)
    out = transform_for_orientation(img, 6)
    assert out.shape == (3, 2, 3)
    assert np.array_equal(out, np.rot90(img, -1))


def test_rotate_90_ccw():
    img = _asymmetric(2, 3)
    assert np.array_equal(transform_for_orientation(img, 8), np.rot90(img, 1))


def test_transpose_swaps_axes():
    img = _asymmetric(2, 3)
    assert np.array_equal(transform_for_orientation(img, 5), np.swapaxes(img, 0, 1))


def test_unknown_code_is_identity():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 99), img)
