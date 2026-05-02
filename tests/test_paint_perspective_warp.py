"""Tests for the 4-corner perspective + distort warps."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.perspective_warp import (
    apply_distort_warp,
    apply_perspective_warp,
    homography_from_corners,
)


# ---------------------------------------------------------------------------
# homography_from_corners
# ---------------------------------------------------------------------------


def test_identity_quad_yields_identity_homography():
    src = np.asarray([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    h = homography_from_corners(src, src)
    assert h is not None
    # Sample point (5, 5, 1) → (5, 5, 1) under identity.
    result = h @ np.array([5.0, 5.0, 1.0])
    result /= result[2]
    np.testing.assert_allclose(result[:2], (5.0, 5.0), atol=1e-6)


def test_translation_quad_yields_translation_homography():
    src = np.asarray([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    dst = src + np.array([3.0, 4.0])
    h = homography_from_corners(src, dst)
    assert h is not None
    result = h @ np.array([5.0, 5.0, 1.0])
    result /= result[2]
    np.testing.assert_allclose(result[:2], (8.0, 9.0), atol=1e-6)


def test_degenerate_collinear_quad_returns_none():
    src = np.asarray([[0, 0], [1, 1], [2, 2], [3, 3]], dtype=np.float64)
    dst = np.asarray([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert homography_from_corners(src, dst) is None


def test_homography_rejects_wrong_shape():
    with pytest.raises(ValueError):
        homography_from_corners(
            np.zeros((3, 2)), np.zeros((4, 2)),
        )


# ---------------------------------------------------------------------------
# apply_perspective_warp
# ---------------------------------------------------------------------------


def _solid_image(w: int, h: int, color: tuple[int, int, int]) -> np.ndarray:
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., :3] = color
    img[..., 3] = 255
    return img


def test_perspective_identity_dst_returns_source_pixels():
    src = _solid_image(8, 8, (200, 100, 50))
    dst_corners = np.asarray(
        [[0, 0], [7, 0], [7, 7], [0, 7]], dtype=np.float64,
    )
    out = apply_perspective_warp(src, dst_corners, output_shape=(8, 8))
    # Centre of the quad must hold the source colour.
    assert tuple(out[4, 4]) == (200, 100, 50, 255)


def test_perspective_outside_quad_is_transparent():
    src = _solid_image(4, 4, (200, 100, 50))
    dst_corners = np.asarray(
        [[2, 2], [5, 2], [5, 5], [2, 5]], dtype=np.float64,
    )
    out = apply_perspective_warp(src, dst_corners, output_shape=(8, 8))
    # Way outside the dst quad → transparent.
    assert out[0, 0, 3] == 0


def test_perspective_rejects_non_rgba():
    src = np.zeros((4, 4, 3), dtype=np.uint8)
    dst = np.asarray([[0, 0], [3, 0], [3, 3], [0, 3]], dtype=np.float64)
    with pytest.raises(ValueError):
        apply_perspective_warp(src, dst, output_shape=(4, 4))


def test_perspective_rejects_non_positive_output():
    src = _solid_image(4, 4, (0, 0, 0))
    dst = np.asarray([[0, 0], [3, 0], [3, 3], [0, 3]], dtype=np.float64)
    with pytest.raises(ValueError):
        apply_perspective_warp(src, dst, output_shape=(0, 4))


def test_perspective_degenerate_dst_returns_blank_canvas():
    src = _solid_image(4, 4, (200, 100, 50))
    # All four corners coincident → zero-area quad → no warp possible.
    dst = np.asarray([[2, 2], [2, 2], [2, 2], [2, 2]], dtype=np.float64)
    out = apply_perspective_warp(src, dst, output_shape=(8, 8))
    assert out.shape == (8, 8, 4)
    assert (out[..., 3] == 0).all()


def test_perspective_translation_moves_quad():
    src = _solid_image(4, 4, (10, 200, 30))
    dst = np.asarray([[2, 2], [5, 2], [5, 5], [2, 5]], dtype=np.float64)
    out = apply_perspective_warp(src, dst, output_shape=(8, 8))
    # Inside the translated quad — colour matches source.
    assert tuple(out[3, 3]) == (10, 200, 30, 255)
    # Outside — transparent.
    assert out[0, 0, 3] == 0


# ---------------------------------------------------------------------------
# apply_distort_warp
# ---------------------------------------------------------------------------


def test_distort_paints_inside_quad():
    src = _solid_image(8, 8, (200, 100, 50))
    dst = np.asarray([[2, 2], [6, 1], [7, 7], [1, 6]], dtype=np.float64)
    out = apply_distort_warp(src, dst, output_shape=(10, 10))
    # The inside of the quad has at least some inked pixels.
    assert (out[..., 3] > 0).any()


def test_distort_outside_quad_is_transparent():
    src = _solid_image(4, 4, (200, 100, 50))
    dst = np.asarray([[2, 2], [5, 2], [5, 5], [2, 5]], dtype=np.float64)
    out = apply_distort_warp(src, dst, output_shape=(8, 8))
    assert out[0, 0, 3] == 0


def test_distort_rejects_non_rgba():
    src = np.zeros((4, 4, 3), dtype=np.uint8)
    dst = np.asarray([[0, 0], [3, 0], [3, 3], [0, 3]], dtype=np.float64)
    with pytest.raises(ValueError):
        apply_distort_warp(src, dst, output_shape=(4, 4))


def test_distort_rejects_low_sample_count():
    src = _solid_image(4, 4, (0, 0, 0))
    dst = np.asarray([[0, 0], [3, 0], [3, 3], [0, 3]], dtype=np.float64)
    with pytest.raises(ValueError):
        apply_distort_warp(src, dst, output_shape=(4, 4), samples_per_axis=1)


def test_distort_rejects_non_positive_output():
    src = _solid_image(4, 4, (0, 0, 0))
    dst = np.asarray([[0, 0], [3, 0], [3, 3], [0, 3]], dtype=np.float64)
    with pytest.raises(ValueError):
        apply_distort_warp(src, dst, output_shape=(0, 0))


def test_distort_does_not_mutate_source():
    src = _solid_image(4, 4, (200, 100, 50))
    snapshot = src.copy()
    dst = np.asarray([[0, 0], [3, 0], [3, 3], [0, 3]], dtype=np.float64)
    apply_distort_warp(src, dst, output_shape=(4, 4))
    np.testing.assert_array_equal(src, snapshot)
