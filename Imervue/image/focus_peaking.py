"""Focus peaking — highlight the in-focus edges of an image.

Outlines high-local-contrast edges (the parts that are sharply in focus) in a
bright marker colour over a dimmed copy of the image, so critical focus can be
confirmed at a glance without pixel-peeping at 100%. This mirrors the focus
peaking on mirrorless cameras and pro RAW viewers.

Pure NumPy: a Sobel gradient magnitude on the luminance channel, thresholded.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
DEFAULT_COLOR = (255, 0, 0)
DEFAULT_THRESHOLD = 0.25
_DIM_FACTOR = 0.55
_SOBEL_X = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)


def _sobel_magnitude(luma: np.ndarray) -> np.ndarray:
    padded = np.pad(luma, 1, mode="edge")
    gx = np.zeros_like(luma)
    gy = np.zeros_like(luma)
    for dy in range(3):
        for dx in range(3):
            window = padded[dy:dy + luma.shape[0], dx:dx + luma.shape[1]]
            gx += _SOBEL_X[dy, dx] * window
            gy += _SOBEL_X[dx, dy] * window  # transpose of Sobel-X is Sobel-Y
    return np.sqrt(gx * gx + gy * gy)


def focus_peaking(
    img: np.ndarray,
    color: tuple[int, int, int] = DEFAULT_COLOR,
    threshold: float = DEFAULT_THRESHOLD,
) -> np.ndarray:
    """Return an HxWx4 RGBA image with sharp edges painted in *color*.

    ``threshold`` in ``[0, 1]`` is the fraction of the peak gradient above
    which a pixel counts as in-focus; lower shows more edges.
    """
    if img.ndim != _RGB_CHANNELS or img.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {img.shape}")
    threshold = float(np.clip(threshold, 0.0, 1.0))
    rgb = img[:, :, :3].astype(np.float32)
    luma = rgb @ _LUMA_WEIGHTS
    magnitude = _sobel_magnitude(luma)
    peak = magnitude.max()
    mask = magnitude >= threshold * peak if peak > 0 else np.zeros(luma.shape, dtype=bool)

    out = np.empty((*luma.shape, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = np.clip(rgb * _DIM_FACTOR, 0, 255).astype(np.uint8)
    out[..., 3] = 255
    out[mask, :3] = color
    return out
