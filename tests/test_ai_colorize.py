"""Tests for the AI colorization heuristic + ONNX plumbing."""
from __future__ import annotations

import numpy as np
import pytest

from ai_colorize.colorize import (
    HEURISTIC_PRESETS,
    ColorizeOptions,
    heuristic_colorize,
    onnx_colorize,
)


def _grayscale(h, w, value):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = value
    arr[..., 1] = value
    arr[..., 2] = value
    arr[..., 3] = 255
    return arr


def _gradient(h, w):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)
    arr[..., 1] = arr[..., 0]
    arr[..., 2] = arr[..., 0]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# heuristic_colorize
# ---------------------------------------------------------------------------


def test_zero_intensity_is_identity():
    base = _grayscale(8, 8, 128)
    out = heuristic_colorize(base, ColorizeOptions(method="sepia", intensity=0.0))
    assert np.array_equal(out, base)


def test_full_sepia_intensity_warms_grey():
    """Mid-grey input through the sepia preset should land in warm tones."""
    base = _grayscale(8, 8, 128)
    out = heuristic_colorize(base, ColorizeOptions(method="sepia", intensity=1.0))
    r, b = int(out[0, 0, 0]), int(out[0, 0, 2])
    assert r > b


def test_cool_preset_pushes_blue():
    base = _grayscale(8, 8, 128)
    out = heuristic_colorize(base, ColorizeOptions(method="cool", intensity=1.0))
    r, b = int(out[0, 0, 0]), int(out[0, 0, 2])
    assert b > r


def test_unknown_preset_falls_back_to_sepia():
    """Unknown preset name should default to sepia, not crash."""
    base = _grayscale(8, 8, 128)
    out = heuristic_colorize(base, ColorizeOptions(method="bogus", intensity=1.0))
    r, b = int(out[0, 0, 0]), int(out[0, 0, 2])
    # Sepia → red dominates over blue
    assert r > b


def test_alpha_preserved():
    base = _grayscale(4, 4, 128)
    base[..., 3] = 80
    out = heuristic_colorize(base, ColorizeOptions(method="sepia", intensity=1.0))
    assert (out[..., 3] == 80).all()


def test_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        heuristic_colorize(arr, ColorizeOptions())


def test_partial_intensity_blends():
    """50% intensity should sit halfway between input and full colourise."""
    base = _grayscale(8, 8, 128)
    full = heuristic_colorize(base, ColorizeOptions(method="sepia", intensity=1.0))
    half = heuristic_colorize(base, ColorizeOptions(method="sepia", intensity=0.5))
    # The half-intensity output's R channel should sit between input (128)
    # and the full-intensity output, within ±2 for rounding.
    target = (128 + int(full[0, 0, 0])) // 2
    assert abs(int(half[0, 0, 0]) - target) <= 2


def test_all_presets_produce_valid_output():
    base = _gradient(16, 16)
    for preset in HEURISTIC_PRESETS:
        out = heuristic_colorize(base, ColorizeOptions(method=preset, intensity=1.0))
        assert out.shape == base.shape
        assert out.dtype == np.uint8
        assert (out[..., 3] == 255).all()


# ---------------------------------------------------------------------------
# onnx_colorize plumbing (no real model, just wiring)
# ---------------------------------------------------------------------------


def test_onnx_colorize_missing_model_raises():
    arr = _grayscale(8, 8, 128)
    pytest.importorskip("onnxruntime")
    with pytest.raises(Exception):  # noqa: B017 - onnxruntime exception types vary
        onnx_colorize(arr, "definitely_does_not_exist.onnx")


def test_onnx_colorize_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        onnx_colorize(arr, "ignored.onnx")
