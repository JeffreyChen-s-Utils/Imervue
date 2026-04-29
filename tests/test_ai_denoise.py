"""Tests for the AI denoise bilateral implementation + ONNX plumbing."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.ai_denoise import (
    BilateralOptions,
    bilateral_denoise,
    onnx_denoise,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def _noisy(h, w, base_rgb, noise_amp=20):
    rng = np.random.default_rng(0)
    arr = _solid(h, w, base_rgb)
    noise = rng.integers(-noise_amp, noise_amp + 1,
                         arr[..., :3].shape, dtype=np.int16)
    arr[..., :3] = np.clip(arr[..., :3].astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return arr


# ---------------------------------------------------------------------------
# bilateral_denoise
# ---------------------------------------------------------------------------


def test_bilateral_zero_blend_is_identity():
    base = _noisy(8, 8, (128, 128, 128))
    out = bilateral_denoise(base, BilateralOptions(blend=0.0))
    assert np.array_equal(out, base)


def test_bilateral_reduces_noise_variance():
    """Denoising a noisy uniform region should shrink its variance."""
    base = _noisy(32, 32, (128, 128, 128), noise_amp=30)
    out = bilateral_denoise(base, BilateralOptions(spatial_radius=4,
                                                   intensity_sigma=40,
                                                   blend=1.0))
    var_before = float(base[..., :3].astype(np.float32).var())
    var_after = float(out[..., :3].astype(np.float32).var())
    assert var_after < var_before


def test_bilateral_preserves_alpha():
    base = _noisy(8, 8, (128, 128, 128))
    base[..., 3] = 80
    out = bilateral_denoise(base, BilateralOptions(blend=1.0))
    assert (out[..., 3] == 80).all()


def test_bilateral_preserves_strong_edges():
    """A black/white step edge should not blur into mid-grey."""
    base = np.zeros((16, 16, 4), dtype=np.uint8)
    base[:, :8, :3] = 0
    base[:, 8:, :3] = 255
    base[..., 3] = 255
    out = bilateral_denoise(base, BilateralOptions(spatial_radius=3,
                                                   intensity_sigma=15,
                                                   blend=1.0))
    # The hard edge column (8) should still differ sharply from column 7.
    delta = abs(int(out[8, 7, 0]) - int(out[8, 8, 0]))
    assert delta > 200


def test_bilateral_radius_clamped():
    """Out-of-range radius should not crash."""
    base = _solid(8, 8, (100, 100, 100))
    out = bilateral_denoise(base, BilateralOptions(spatial_radius=999))
    assert out.shape == base.shape


def test_bilateral_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        bilateral_denoise(arr)


# ---------------------------------------------------------------------------
# onnx_denoise (we don't test inference here — just wiring)
# ---------------------------------------------------------------------------


def test_onnx_denoise_missing_model_raises():
    """No model file → onnxruntime surfaces a load error.

    The exact exception class varies by onnxruntime version (Fail /
    InvalidProtobuf / NoSuchFile), so we just assert that *some* exception
    propagates rather than the function silently returning.
    """
    arr = _solid(8, 8, (128, 128, 128))
    pytest.importorskip("onnxruntime")
    with pytest.raises(Exception):  # noqa: B017 - onnxruntime exception types vary
        onnx_denoise(arr, "definitely_does_not_exist.onnx")


def test_onnx_denoise_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        onnx_denoise(arr, "ignored.onnx")
