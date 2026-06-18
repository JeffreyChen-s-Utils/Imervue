"""Local-contrast develop adjustments — clarity and texture.

Clarity and Texture are the two local-contrast sliders every modern editor
ships (Lightroom Basic panel, Capture One, Photoshop 27.3 adjustment layers).
Both are luminance unsharp-mask operators; they differ only in scale and tonal
weighting:

* clarity — large-radius local contrast weighted toward the midtones, so it
  adds "punch" to skies and architecture without crushing the black/white
  points.
* texture — small-radius high-frequency contrast applied evenly. Positive
  sharpens fine detail (foliage, fabric); negative softens it while keeping
  edges crisper than a plain blur.

Pure NumPy (separable Gaussian), so this ships in the main program.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_AMOUNT_LIMIT = 4.0
CLARITY_RADIUS = 24
TEXTURE_RADIUS = 3
_CLARITY_GAIN = 0.9
_TEXTURE_GAIN = 1.1


def apply_clarity(arr: np.ndarray, amount: float) -> np.ndarray:
    """Midtone-weighted large-radius local contrast. ``amount`` in [-1, 1]."""
    return _unsharp_luma(arr, amount * _CLARITY_GAIN, CLARITY_RADIUS, midtone=True)


def apply_texture(arr: np.ndarray, amount: float) -> np.ndarray:
    """Small-radius high-frequency local contrast. ``amount`` in [-1, 1]."""
    return _unsharp_luma(arr, amount * _TEXTURE_GAIN, TEXTURE_RADIUS, midtone=False)


def _unsharp_luma(
    arr: np.ndarray, amount: float, radius: int, *, midtone: bool,
) -> np.ndarray:
    _validate(arr)
    amount = float(np.clip(amount, -_AMOUNT_LIMIT, _AMOUNT_LIMIT))
    if amount == 0.0:
        return arr.copy()
    rgb = arr[..., :3].astype(np.float32)
    lum = rgb @ _LUMA_WEIGHTS
    detail = lum - blur_plane(lum, radius)
    if midtone:
        detail = detail * _midtone_weight(lum)
    out = rgb + amount * detail[..., None]
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def _midtone_weight(lum: np.ndarray) -> np.ndarray:
    """Bell curve peaking at mid-grey, zero at pure black / white."""
    norm = lum / _MAX_8BIT * 2.0 - 1.0
    return np.clip(1.0 - norm * norm, 0.0, 1.0)


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


# --- separable Gaussian (pure numpy) ---------------------------------------

def blur_plane(plane: np.ndarray, radius: int) -> np.ndarray:
    """Separable Gaussian blur of a single float plane."""
    kernel = _gaussian_kernel_1d(radius)
    out = _convolve_axis(plane.astype(np.float32), kernel, axis=0)
    return _convolve_axis(out, kernel, axis=1)


def _gaussian_kernel_1d(radius: int) -> np.ndarray:
    sigma = max(1.0, radius / 2.0)
    half = max(1, int(round(sigma * 3)))
    idx = np.arange(-half, half + 1, dtype=np.float32)
    kernel = np.exp(-(idx ** 2) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    return kernel


def _convolve_axis(plane: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    pad = kernel.size // 2
    pad_width = [(0, 0), (0, 0)]
    pad_width[axis] = (pad, pad)
    padded = np.pad(plane, pad_width, mode="edge")
    out = np.zeros_like(plane)
    for i, weight in enumerate(kernel):
        sl = [slice(None), slice(None)]
        sl[axis] = slice(i, i + plane.shape[axis])
        out += weight * padded[tuple(sl)]
    return out
