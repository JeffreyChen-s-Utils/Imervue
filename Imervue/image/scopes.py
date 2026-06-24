"""Video-style scopes — luminance waveform and RGB parade.

A waveform plots image *column* on the x-axis and pixel *brightness* on the
y-axis, with brightness-of-plot encoding how many pixels fall there. It is the
objective exposure read-out that the eye cannot give. The RGB parade is the
same idea per channel, drawn in each channel's colour so white-balance and
channel clipping are visible at a glance.

Pure NumPy: a fully-vectorised per-column ``bincount`` builds the scope, and
the input is downscaled first so the cost is bounded regardless of resolution.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
SCOPE_HEIGHT = 256
_MAX_SCOPE_WIDTH = 512
_LEVELS = 256


def _rgb_view(img: np.ndarray) -> np.ndarray:
    if img.ndim != _RGB_CHANNELS or img.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {img.shape}")
    return img[:, :, :3]


def _downscale_width(rgb: np.ndarray) -> np.ndarray:
    """Column-subsample so the scope width stays bounded; rows are untouched."""
    width = rgb.shape[1]
    if width <= _MAX_SCOPE_WIDTH:
        return rgb
    step = int(np.ceil(width / _MAX_SCOPE_WIDTH))
    return rgb[:, ::step]


def _channel_waveform(plane: np.ndarray) -> np.ndarray:
    """Return a ``SCOPE_HEIGHT`` x W uint8 intensity map for one 8-bit plane."""
    _, width = plane.shape
    # Offset each column into its own 256-bin block so one bincount does all.
    flat = plane.astype(np.int64) + _LEVELS * np.arange(width)[None, :]
    counts = np.bincount(flat.ravel(), minlength=_LEVELS * width)
    counts = counts.reshape(width, _LEVELS).T.astype(np.float32)  # (256, W)
    peak = counts.max()
    if peak > 0:
        counts = np.sqrt(counts / peak)  # sqrt lifts sparse traces into view
    intensity = np.clip(counts * 255.0, 0, 255).astype(np.uint8)
    return intensity[::-1]  # row 0 = brightest level, drawn at the top


def compute_waveform(img: np.ndarray) -> np.ndarray:
    """Luminance waveform as a SCOPE_HEIGHT x W uint8 grayscale image."""
    rgb = _downscale_width(_rgb_view(img))
    luma = np.clip(np.rint(rgb.astype(np.float32) @ _LUMA_WEIGHTS), 0, 255).astype(np.uint8)
    return _channel_waveform(luma)


def compute_parade(img: np.ndarray) -> np.ndarray:
    """RGB parade as a SCOPE_HEIGHT x W x3 uint8 image, one trace per channel colour."""
    rgb = _downscale_width(_rgb_view(img))
    out = np.zeros((SCOPE_HEIGHT, rgb.shape[1], _RGB_CHANNELS), dtype=np.uint8)
    for channel in range(_RGB_CHANNELS):
        out[..., channel] = _channel_waveform(rgb[..., channel])
    return out
