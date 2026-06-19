"""No-reference image-quality / aesthetics metrics.

Single-number diagnostics computable without a reference image or a trained
model: colourfulness (Hasler-Süsstrunk), tonal entropy, RMS contrast, edge
density and a noise-sigma estimate. Useful as an at-a-glance quality readout
and as extra axes alongside the composite cull score. Pure NumPy.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.sharpness import to_luma

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_COLORFULNESS_MEAN_WEIGHT = 0.3
_EDGE_THRESHOLD = 24.0
# Immerkær fast-noise Laplacian kernel.
_NOISE_KERNEL = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def colorfulness(arr: np.ndarray) -> float:
    """Hasler-Süsstrunk colourfulness — higher is more vivid (grayscale ≈ 0)."""
    rgb = arr[..., :3].astype(np.float64)
    rg = rgb[..., 0] - rgb[..., 1]
    yb = 0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]
    std = np.hypot(rg.std(), yb.std())
    mean = np.hypot(rg.mean(), yb.mean())
    return float(std + _COLORFULNESS_MEAN_WEIGHT * mean)


def entropy(arr: np.ndarray) -> float:
    """Shannon entropy of the luminance histogram, in bits (0–8)."""
    luma = np.clip(np.rint(to_luma(arr)), 0, 255).astype(np.int64)
    counts = np.bincount(luma.ravel(), minlength=256).astype(np.float64)
    probs = counts[counts > 0] / counts.sum()
    return float(-np.sum(probs * np.log2(probs)))


def rms_contrast(arr: np.ndarray) -> float:
    """Root-mean-square contrast — the standard deviation of luminance."""
    return float(to_luma(arr).std())


def _convolve3(plane: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, 1, mode="edge")
    out = np.zeros_like(plane, dtype=np.float64)
    for dy in range(3):
        for dx in range(3):
            out += kernel[dy, dx] * padded[dy:dy + plane.shape[0], dx:dx + plane.shape[1]]
    return out


def edge_density(arr: np.ndarray, threshold: float = _EDGE_THRESHOLD) -> float:
    """Fraction of pixels whose Sobel gradient magnitude exceeds *threshold*."""
    luma = to_luma(arr)
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
    gx = _convolve3(luma, sobel_x)
    gy = _convolve3(luma, sobel_x.T)
    return float(np.mean(np.hypot(gx, gy) > threshold))


def noise_sigma(arr: np.ndarray) -> float:
    """Immerkær fast noise-standard-deviation estimate of the luminance."""
    luma = to_luma(arr)
    if luma.shape[0] < 3 or luma.shape[1] < 3:
        return 0.0
    response = np.abs(_convolve3(luma, _NOISE_KERNEL))
    h, w = luma.shape
    scale = np.sqrt(np.pi / 2.0) / (6.0 * (w - 2) * (h - 2))
    return float(scale * response[1:-1, 1:-1].sum())


def quality_metrics(arr: np.ndarray) -> dict[str, float]:
    """Return all no-reference metrics for *arr* as a name→value dict."""
    _validate(arr)
    return {
        "colorfulness": colorfulness(arr),
        "entropy": entropy(arr),
        "rms_contrast": rms_contrast(arr),
        "edge_density": edge_density(arr),
        "noise_sigma": noise_sigma(arr),
    }
