"""Tests for no-reference quality metrics."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.quality_metrics import (
    colorfulness,
    edge_density,
    entropy,
    noise_sigma,
    quality_metrics,
    rms_contrast,
)


def _rgba(rgb, h=24, w=24):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = rgb
    arr[..., 3] = 255
    return arr


def _noise_rgba(h=24, w=24, seed=0):
    rng = np.random.default_rng(seed)
    rgb = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _edge_rgba(h=24, w=24):
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:, w // 2 :] = 255
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_colorfulness_gray_near_zero():
    assert colorfulness(_rgba((128, 128, 128))) < 1.0
    assert colorfulness(_noise_rgba()) > colorfulness(_rgba((128, 128, 128)))


def test_entropy_flat_zero_noise_high():
    assert entropy(_rgba((100, 100, 100))) == 0.0  # NOSONAR - flat image has one level
    assert entropy(_noise_rgba()) > 4.0


def test_rms_contrast_flat_zero():
    assert rms_contrast(_rgba((100, 100, 100))) < 1e-6


def test_edge_density_edge_vs_flat():
    assert edge_density(_edge_rgba()) > 0.0
    assert edge_density(_rgba((100, 100, 100))) == 0.0  # NOSONAR - flat has no edges


def test_noise_sigma_flat_low():
    assert noise_sigma(_rgba((100, 100, 100))) < 1.0
    assert noise_sigma(_noise_rgba()) > 5.0


def test_quality_metrics_keys():
    metrics = quality_metrics(_noise_rgba())
    assert set(metrics) == {
        "colorfulness", "entropy", "rms_contrast", "edge_density", "noise_sigma"}


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        quality_metrics(np.zeros((8, 8), dtype=np.uint8))
