"""Tests for the AI Style Transfer ONNX wrapper.

Plugin internals are reachable thanks to the conftest sys.path injection
that puts ``plugins/`` on the path.
"""
from __future__ import annotations

import numpy as np
import pytest

from ai_style_transfer.style_transfer import (
    INTENSITY_MAX,
    INTENSITY_MIN,
    StyleTransferOptions,
    _decode_output,
    stylise,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Output decoder — covers the three branches without needing a real model
# ---------------------------------------------------------------------------


def test_decode_output_handles_zero_one_range():
    out = np.linspace(0.0, 1.0, 4 * 4 * 3, dtype=np.float32).reshape(1, 3, 4, 4)
    decoded = _decode_output(out)
    assert decoded.shape == (4, 4, 3)
    assert decoded.min() >= 0.0
    assert decoded.max() <= 1.0


def test_decode_output_handles_zero_255_range():
    """Pytorch fast_neural_style style export: values in [0, 255]."""
    raw = np.linspace(0.0, 255.0, 4 * 4 * 3, dtype=np.float32).reshape(1, 3, 4, 4)
    decoded = _decode_output(raw)
    # Should be normalised to [0, 1]
    assert decoded.max() <= 1.0
    assert decoded.min() >= 0.0
    # And cover the full range, not collapsed to a constant
    assert decoded.max() - decoded.min() > 0.5


def test_decode_output_falls_back_to_minmax_for_weird_range():
    """Out-of-band values should be min/max stretched, not collapsed to zero."""
    # rgb_min < -5 forces the fallback path (heuristic B requires >= -5)
    raw = np.linspace(-50.0, 50.0, 4 * 4 * 3, dtype=np.float32).reshape(1, 3, 4, 4)
    decoded = _decode_output(raw)
    assert decoded.min() >= 0.0
    assert decoded.max() <= 1.0
    assert decoded.max() - decoded.min() > 0.9


def test_decode_output_rejects_wrong_shape():
    bad = np.zeros((1, 4, 4, 4), dtype=np.float32)  # 4 channels not 3
    with pytest.raises(ValueError):
        _decode_output(bad)


def test_decode_output_rejects_2d_input():
    bad = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        _decode_output(bad)


# ---------------------------------------------------------------------------
# stylise — input validation + ONNX plumbing (no real model)
# ---------------------------------------------------------------------------


def test_stylise_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        stylise(arr, StyleTransferOptions(model_path="ignored.onnx"))


def test_stylise_missing_model_raises():
    arr = _solid(8, 8, (128, 128, 128))
    pytest.importorskip("onnxruntime")
    with pytest.raises(Exception):  # noqa: B017 - onnxruntime exception types vary
        stylise(arr, StyleTransferOptions(
            model_path="definitely_does_not_exist.onnx",
        ))


def test_intensity_constants_are_unit():
    assert pytest.approx(0.0) == INTENSITY_MIN
    assert pytest.approx(1.0) == INTENSITY_MAX


# ---------------------------------------------------------------------------
# Plugin module discovery (smoke)
# ---------------------------------------------------------------------------


def test_plugin_module_imports_without_models():
    """Importing the plugin should not fail when no .onnx model exists."""
    from ai_style_transfer import ai_style_transfer_plugin
    assert ai_style_transfer_plugin.AIStyleTransferPlugin.plugin_name
