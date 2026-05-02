"""ONNX-driven fast neural style transfer.

Designed around the canonical PyTorch ``fast_neural_style`` family
(Johnson et al. 2016): single feed-forward pass, takes an RGB image,
produces a stylised RGB image of the same shape. Models are typically
exported to ONNX and dropped into ``plugins/ai_style_transfer/models/``.

Two output conventions are auto-detected:

* ``[0, 255]`` float32 (original PyTorch fast_neural_style export) —
  divided by 255 before clipping to display range.
* ``[0, 1]`` float32 (most modern exports) — used directly.

The detection picks the one whose values mostly fall inside the [0, 1]
range; if neither does, the output is simply rescaled by min/max so
the user still gets *something* on screen.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.style_transfer")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0


@dataclass(frozen=True)
class StyleTransferOptions:
    """Per-call tuning for :func:`stylise`."""

    model_path: str
    intensity: float = 1.0   # blend with the original


def stylise(arr: np.ndarray, options: StyleTransferOptions) -> np.ndarray:
    """Run the configured ONNX style model on ``arr``.

    Returns the same shape as the input. Both ``onnxruntime`` and a
    real model file are required — ImportError / OSError surfaces to
    the caller.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"stylise expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError(
            "onnxruntime is required for AI Style Transfer.",
        ) from exc

    session = ort.InferenceSession(
        str(options.model_path), providers=ort.get_available_providers(),
    )
    input_name = session.get_inputs()[0].name

    rgb = arr[..., :3].astype(np.float32)
    # Fast-neural-style PyTorch models expect raw [0, 255] RGB; modern
    # ONNX exports often expect [0, 1]. We try [0, 255] first and let
    # the per-output normaliser figure it out — it's cheap.
    tensor = np.transpose(rgb, (2, 0, 1))[None, ...]
    output = session.run(None, {input_name: tensor})[0]
    stylised = _decode_output(output)

    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, options.intensity))
    if intensity < 1.0:
        original = rgb / 255.0
        stylised = original * (1.0 - intensity) + stylised * intensity

    out = arr.copy()
    out[..., :3] = np.clip(stylised * 255.0, 0, 255).astype(np.uint8)
    return out


def _decode_output(output: np.ndarray) -> np.ndarray:
    """Normalise an arbitrary model output to HxWx3 float in [0, 1]."""
    if output.ndim != 4 or output.shape[0] != 1 or output.shape[1] != 3:
        raise ValueError(
            f"unexpected style-transfer output shape: {output.shape}",
        )
    rgb = np.transpose(output[0], (1, 2, 0))   # HxWx3 float
    rgb_min, rgb_max = float(rgb.min()), float(rgb.max())

    # Heuristic A: if values fit roughly in [0, 1], assume that range.
    if rgb_max <= 1.5 and rgb_min >= -0.05:
        return np.clip(rgb, 0.0, 1.0)

    # Heuristic B: classic [0, 255] PyTorch fast_neural_style output.
    if rgb_max <= 260 and rgb_min >= -5:
        return np.clip(rgb / 255.0, 0.0, 1.0)

    # Last resort — rescale by min/max so the user still sees something.
    span = max(1e-6, rgb_max - rgb_min)
    return np.clip((rgb - rgb_min) / span, 0.0, 1.0)
