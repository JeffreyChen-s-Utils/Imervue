"""Calibration / test-chart generator.

Synthesises standard reference patterns — SMPTE-style 75% colour bars, a
grayscale step wedge, a linear gradient ramp, a checkerboard and a solid fill —
for monitor / print calibration and pipeline testing. Pure NumPy.
"""
from __future__ import annotations

import numpy as np

_RGBA_CHANNELS = 4
_OPAQUE = 255
_RGB_CHANNELS = 3

SMPTE = "smpte"
GRAYSCALE = "grayscale"
GRADIENT = "gradient"
CHECKER = "checker"
SOLID = "solid"
PATTERNS = (SMPTE, GRAYSCALE, GRADIENT, CHECKER, SOLID)

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
_CHECKER_SIZE = 32
_GRAY_STEPS = 11
# SMPTE 75% bars, left→right.
_SMPTE_BARS = (
    (180, 180, 180), (180, 180, 16), (16, 180, 180), (16, 180, 16),
    (180, 16, 180), (180, 16, 16), (16, 16, 180), (16, 16, 16),
)


def _rgba(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    out = np.empty((h, w, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = rgb
    out[..., 3] = _OPAQUE
    return out


def _columns(width: int, colors) -> np.ndarray:
    edges = np.linspace(0, width, len(colors) + 1).astype(int)
    row = np.zeros((width, _RGB_CHANNELS), dtype=np.uint8)
    for i, color in enumerate(colors):
        row[edges[i]:edges[i + 1]] = color
    return row


def generate_chart(
    pattern: str = SMPTE,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    color: tuple[int, int, int] = (128, 128, 128),
) -> np.ndarray:
    """Return an HxWx4 RGBA test chart of the given *pattern*."""
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern {pattern!r}; expected one of {PATTERNS}")
    width = max(1, int(width))
    height = max(1, int(height))
    if pattern == SMPTE:
        rgb = np.broadcast_to(_columns(width, _SMPTE_BARS), (height, width, _RGB_CHANNELS))
    elif pattern == GRAYSCALE:
        steps = [(v, v, v) for v in np.linspace(0, 255, _GRAY_STEPS).astype(int)]
        rgb = np.broadcast_to(_columns(width, steps), (height, width, _RGB_CHANNELS))
    elif pattern == GRADIENT:
        ramp = np.linspace(0, 255, width).astype(np.uint8)
        rgb = np.repeat(ramp[None, :, None], height, axis=0).repeat(_RGB_CHANNELS, axis=2)
    elif pattern == CHECKER:
        yy, xx = np.mgrid[0:height, 0:width]
        mask = ((xx // _CHECKER_SIZE + yy // _CHECKER_SIZE) & 1).astype(np.uint8)
        value = (mask * 200 + 30).astype(np.uint8)
        rgb = np.stack([value, value, value], axis=-1)
    else:  # SOLID
        rgb = np.broadcast_to(np.array(color, dtype=np.uint8), (height, width, _RGB_CHANNELS))
    return _rgba(np.ascontiguousarray(rgb))
