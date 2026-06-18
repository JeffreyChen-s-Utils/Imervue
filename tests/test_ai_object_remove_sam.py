"""Tests for SAM masking helpers (pure pre/post + model discovery)."""
from __future__ import annotations

import numpy as np
import pytest

from ai_object_remove.sam import (
    SAM_TARGET,
    binarize_mask,
    discover_sam_models,
    longest_side_scale,
    normalize_image,
    preprocess_point_coords,
    preprocess_point_labels,
    resized_hw,
    sam_mask,
)


# ---------------------------------------------------------------------------
# scaling
# ---------------------------------------------------------------------------


def test_longest_side_scale():
    assert longest_side_scale(1000, 2000) == pytest.approx(0.512)
    assert longest_side_scale(0, 0) == 1.0


def test_resized_hw_caps_longest_side():
    assert resized_hw(1000, 2000) == (512, 1024)


# ---------------------------------------------------------------------------
# point prompts
# ---------------------------------------------------------------------------


def test_preprocess_point_coords_scales_and_pads():
    coords = preprocess_point_coords([(10, 20)], 2.0)
    assert coords.shape == (1, 2, 2)
    assert list(coords[0, 0]) == [20.0, 40.0]
    assert list(coords[0, 1]) == [0.0, 0.0]  # padding point
    assert coords.dtype == np.float32


def test_preprocess_point_labels_appends_padding():
    labels = preprocess_point_labels([1])
    assert labels.shape == (1, 2)
    assert labels[0, 0] == 1.0
    assert labels[0, 1] == -1.0


# ---------------------------------------------------------------------------
# image normalisation
# ---------------------------------------------------------------------------


def test_normalize_image_shape_and_padding():
    resized = np.zeros((2, 3, 3), dtype=np.float32)
    out = normalize_image(resized)
    assert out.shape == (1, 3, SAM_TARGET, SAM_TARGET)
    # Padding beyond the resized region is exactly zero.
    assert np.all(out[:, :, 2:, :] == 0)
    assert np.all(out[:, :, :, 3:] == 0)
    # Inside the region the (zero) pixels are mean/std-normalised → non-zero.
    assert out[0, 0, 0, 0] != 0


# ---------------------------------------------------------------------------
# mask thresholding
# ---------------------------------------------------------------------------


def test_binarize_mask_reduces_and_thresholds():
    logits = np.array([[[[-1.0, 2.0], [3.0, -4.0]]]], dtype=np.float32)
    mask = binarize_mask(logits)
    assert mask.shape == (2, 2)
    assert mask.tolist() == [[False, True], [True, False]]


# ---------------------------------------------------------------------------
# model discovery
# ---------------------------------------------------------------------------


def test_discover_sam_models_empty_dir(tmp_path):
    assert discover_sam_models(tmp_path) == (None, None)


def test_discover_sam_models_finds_pair(tmp_path):
    (tmp_path / "vit_encoder.onnx").write_bytes(b"\x00")
    (tmp_path / "sam_decoder.onnx").write_bytes(b"\x00")
    encoder, decoder = discover_sam_models(tmp_path)
    assert encoder.endswith("vit_encoder.onnx")
    assert decoder.endswith("sam_decoder.onnx")


def test_discover_sam_models_missing_encoder(tmp_path):
    (tmp_path / "model_decoder.onnx").write_bytes(b"\x00")
    assert discover_sam_models(tmp_path) == (None, str(tmp_path / "model_decoder.onnx"))


# ---------------------------------------------------------------------------
# runtime guard
# ---------------------------------------------------------------------------


def test_sam_mask_missing_runtime_raises(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    with pytest.raises(ImportError):
        sam_mask(arr, [(4, 4)], [1], "enc.onnx", "dec.onnx")


def test_sam_mask_rejects_non_image():
    with pytest.raises(ValueError):
        sam_mask(np.zeros((8, 8), dtype=np.uint8), [(1, 1)], [1], "e.onnx", "d.onnx")
