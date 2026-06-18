"""Tests for the Laplacian-variance sharpness metric."""
from __future__ import annotations

import numpy as np

from Imervue.image.sharpness import (
    laplacian_variance,
    select_blurry,
    sharpness_score,
    to_luma,
)


def _checkerboard(n: int = 16) -> np.ndarray:
    return ((np.indices((n, n)).sum(axis=0) % 2) * 255).astype(np.uint8)


def test_to_luma_passes_through_grayscale():
    g = np.zeros((3, 4), dtype=np.uint8)
    assert to_luma(g).shape == (3, 4)


def test_to_luma_reduces_rgb():
    rgb = np.zeros((3, 4, 3), dtype=np.uint8)
    assert to_luma(rgb).shape == (3, 4)


def test_laplacian_variance_uniform_is_zero():
    assert laplacian_variance(np.full((8, 8), 128.0)) == 0.0


def test_laplacian_variance_empty_is_zero():
    assert laplacian_variance(np.zeros((0, 0))) == 0.0


def test_sharp_scores_higher_than_blurry():
    sharp = sharpness_score(_checkerboard())
    blurry = sharpness_score(np.full((16, 16), 128.0))
    assert sharp > blurry
    assert blurry == 0.0


def test_select_blurry_filters_below_threshold():
    scores = [("a.png", 50.0), ("b.png", 250.0), ("c.png", 99.9)]
    assert select_blurry(scores, threshold=100.0) == ["a.png", "c.png"]
