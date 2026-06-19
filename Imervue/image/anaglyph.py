"""Anaglyph 3D — combine a stereo pair into a single red-cyan image.

The left view feeds the red channel and the right view the cyan (green+blue),
so red-cyan glasses recover depth. Several encodings are offered: Dubois
(optimised, low ghosting), full colour, half-colour grey, and the basic true
anaglyph. Pure NumPy + Pillow (only for resizing a mismatched right view).
"""
from __future__ import annotations

import numpy as np
from PIL import Image

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_MAX = 255.0

DUBOIS = "dubois"
COLOR = "color"
GRAY = "gray"
TRUE = "true"
METHODS = (DUBOIS, COLOR, GRAY, TRUE)

# Dubois red-cyan matrices (output_channel x input_channel), on 0..1 linear-ish RGB.
_DUBOIS_LEFT = np.array([
    [0.437, 0.449, 0.164],
    [-0.062, -0.062, -0.024],
    [-0.048, -0.050, -0.017],
], dtype=np.float32)
_DUBOIS_RIGHT = np.array([
    [-0.011, -0.032, -0.007],
    [0.377, 0.761, 0.009],
    [-0.026, -0.093, 1.234],
], dtype=np.float32)


def _validate(arr: np.ndarray, name: str) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"{name} must be HxWx3/4 image, got {arr.shape}")


def _match_size(right: np.ndarray, height: int, width: int) -> np.ndarray:
    if right.shape[:2] == (height, width):
        return right
    mode = "RGBA" if right.shape[2] == _RGBA_CHANNELS else "RGB"
    resized = Image.fromarray(right, mode).resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(resized)


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb @ _LUMA_WEIGHTS


def anaglyph(left: np.ndarray, right: np.ndarray, method: str = DUBOIS) -> np.ndarray:
    """Combine *left* / *right* views into an HxWx4 RGBA red-cyan anaglyph."""
    _validate(left, "left")
    _validate(right, "right")
    h, w = left.shape[:2]
    lhs = left[..., :3].astype(np.float32)
    rhs = _match_size(right, h, w)[..., :3].astype(np.float32)
    out_rgb = _encode(lhs, rhs, method)
    out = np.empty((h, w, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = np.clip(np.rint(out_rgb), 0, 255).astype(np.uint8)
    out[..., 3] = _OPAQUE
    return out


def _encode(lhs: np.ndarray, rhs: np.ndarray, method: str) -> np.ndarray:
    if method == DUBOIS:
        return (lhs / _MAX) @ _DUBOIS_LEFT.T * _MAX + (rhs / _MAX) @ _DUBOIS_RIGHT.T * _MAX
    if method == GRAY:
        left_luma, right_luma = _luma(lhs), _luma(rhs)
        return np.stack([left_luma, right_luma, right_luma], axis=-1)
    if method == TRUE:
        zeros = np.zeros(lhs.shape[:2], dtype=np.float32)
        return np.stack([_luma(lhs), zeros, _luma(rhs)], axis=-1)
    # COLOR: left red, right green/blue.
    return np.stack([lhs[..., 0], rhs[..., 1], rhs[..., 2]], axis=-1)
