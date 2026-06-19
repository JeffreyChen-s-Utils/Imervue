"""Generative outpaint — extend the canvas and fill the new border.

Outpainting is inpainting with an inverted mask: place the original image into a
larger canvas and fill the surrounding border. This reuses the model-free
diffusion inpainter (:func:`Imervue.image.inpaint.inpaint_diffusion`), so it
works offline; a generative ONNX path can layer on later behind the plugin.

The canvas-expansion and mask construction are pure NumPy and unit-tested.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.inpaint import DEFAULT_ITERATIONS, inpaint_diffusion

PAD_MIN = 0
PAD_MAX = 2048
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255


def _to_rgba(arr: np.ndarray) -> np.ndarray:
    if arr.shape[2] == _RGBA_CHANNELS:
        return arr
    alpha = np.full((*arr.shape[:2], 1), _OPAQUE, dtype=np.uint8)
    return np.concatenate([arr, alpha], axis=2)


def expand_canvas(arr: np.ndarray, left: int, top: int,
                  right: int, bottom: int) -> tuple[np.ndarray, np.ndarray]:
    """Place *arr* into a larger RGBA canvas; return ``(canvas, fill_mask)``.

    ``fill_mask`` is True over the new border (the region to outpaint) and
    False over the original image.
    """
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")
    h, w = arr.shape[:2]
    pad = [max(0, int(v)) for v in (left, top, right, bottom)]
    left, top, right, bottom = pad
    canvas = np.zeros((h + top + bottom, w + left + right, _RGBA_CHANNELS),
                      dtype=np.uint8)
    canvas[top:top + h, left:left + w] = _to_rgba(arr)
    mask = np.ones(canvas.shape[:2], dtype=bool)
    mask[top:top + h, left:left + w] = False
    return canvas, mask


def outpaint(arr: np.ndarray, padding: int,
             iterations: int = DEFAULT_ITERATIONS) -> np.ndarray:
    """Extend *arr* by *padding* px on every side and fill the border."""
    pad = max(PAD_MIN, min(PAD_MAX, int(padding)))
    if pad == 0:
        return _to_rgba(arr)
    canvas, mask = expand_canvas(arr, pad, pad, pad, pad)
    return inpaint_diffusion(canvas, mask, iterations=iterations)
