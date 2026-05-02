"""Image denoising — bilateral-style filter + ONNX plumbing.

Two methods are exposed:

* :func:`bilateral_denoise` — pure-numpy edge-preserving denoiser. Uses a
  separable Gaussian on the spatial domain combined with an intensity
  weighting term. Works without any ML model and ships in the default
  dependency set.
* :func:`onnx_denoise` — loads a user-supplied ONNX model (NAFNet,
  DnCNN, SCUNet, …) and runs it through ``onnxruntime``. The model
  signature must be ``(1, 3, H, W) → (1, 3, H, W)`` float32 in [0, 1].
  Both packages are optional; ImportError surfaces to the caller.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.ai_denoise")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0
SPATIAL_RADIUS_MIN = 1
SPATIAL_RADIUS_MAX = 12


@dataclass(frozen=True)
class BilateralOptions:
    """Tuning for :func:`bilateral_denoise`."""

    spatial_radius: int = 4         # search window half-size
    intensity_sigma: float = 30.0   # tonal-distance sigma in 0..255 space
    blend: float = 1.0              # 0..1 mix between original and denoised


def bilateral_denoise(arr: np.ndarray, options: BilateralOptions | None = None) -> np.ndarray:
    """Edge-preserving denoise via spatially-weighted intensity averaging."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"bilateral_denoise expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    options = options or BilateralOptions()
    radius = max(SPATIAL_RADIUS_MIN, min(SPATIAL_RADIUS_MAX, options.spatial_radius))
    sigma_i = max(1.0, float(options.intensity_sigma))
    blend = max(0.0, min(1.0, float(options.blend)))
    if blend <= 0.0:
        return arr

    rgb = arr[..., :3].astype(np.float32)
    denoised = np.empty_like(rgb)
    for channel in range(3):
        denoised[..., channel] = _bilateral_channel(
            rgb[..., channel], radius, sigma_i,
        )
    if blend < 1.0:
        denoised = rgb * (1.0 - blend) + denoised * blend
    out = arr.copy()
    out[..., :3] = np.clip(denoised, 0, 255).astype(np.uint8)
    return out


def onnx_denoise(arr: np.ndarray, model_path: str, blend: float = 1.0) -> np.ndarray:
    """Run an external ONNX denoise model on ``arr``.

    The model must accept ``(1, 3, H, W)`` RGB float32 in [0, 1] and
    return the same shape. Both ``onnxruntime`` and an actual model file
    are required — ImportError / OSError surface to the caller.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"onnx_denoise expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError(
            "onnxruntime is required for the AI denoise model path."
        ) from exc

    session = ort.InferenceSession(
        str(model_path), providers=ort.get_available_providers(),
    )
    input_name = session.get_inputs()[0].name
    rgb = arr[..., :3].astype(np.float32) / 255.0
    # NHWC → NCHW
    tensor = np.transpose(rgb, (2, 0, 1))[None, ...]
    output = session.run(None, {input_name: tensor})[0]
    # NCHW → HWC
    denoised = np.transpose(output[0], (1, 2, 0))

    blend = max(0.0, min(1.0, float(blend)))
    if blend < 1.0:
        denoised = rgb * (1.0 - blend) + denoised * blend
    out = arr.copy()
    out[..., :3] = np.clip(denoised * 255.0, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Bilateral implementation
# ---------------------------------------------------------------------------


def _bilateral_channel(plane: np.ndarray, radius: int, sigma_i: float) -> np.ndarray:
    """Spatial × intensity weighted average for one channel."""
    h, w = plane.shape
    accumulated = np.zeros_like(plane, dtype=np.float32)
    weights = np.zeros_like(plane, dtype=np.float32)
    sigma_s = max(0.5, radius / 2.0)

    # Build the spatial Gaussian weights for each (dy, dx) offset.
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            spatial_w = np.exp(-(dy * dy + dx * dx) / (2.0 * sigma_s * sigma_s))
            shifted = _shift(plane, dy, dx)
            intensity_w = np.exp(
                -((shifted - plane) ** 2) / (2.0 * sigma_i * sigma_i),
            )
            w_total = spatial_w * intensity_w
            accumulated += shifted * w_total
            weights += w_total
    return accumulated / np.maximum(weights, 1e-6)


def _shift(plane: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Shift ``plane`` by (dy, dx) with edge-replicating padding."""
    h, w = plane.shape
    y_src = np.clip(np.arange(h) + dy, 0, h - 1)
    x_src = np.clip(np.arange(w) + dx, 0, w - 1)
    return plane[y_src][:, x_src]
