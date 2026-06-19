"""Scientific colour maps — map luminance through a perceptual gradient.

Re-colours a grayscale/luminance image through a continuous colour map
(viridis, magma, jet) so subtle luminance structure becomes visible — the data
visualisation counterpart to the discrete IRE false-colour exposure view.

Pure NumPy: each map is built once from a few anchor colours by linear
interpolation into a 256-entry lookup table, then applied by indexing.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.sharpness import to_luma

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_LEVELS = 256

# Anchor colours (position 0..1 → RGB) approximating each named map.
_ANCHORS = {
    "viridis": [
        (0.0, (68, 1, 84)), (0.25, (59, 82, 139)), (0.5, (33, 145, 140)),
        (0.75, (94, 201, 98)), (1.0, (253, 231, 37)),
    ],
    "magma": [
        (0.0, (0, 0, 4)), (0.25, (80, 18, 123)), (0.5, (182, 54, 121)),
        (0.75, (251, 136, 97)), (1.0, (252, 253, 191)),
    ],
    "jet": [
        (0.0, (0, 0, 131)), (0.125, (0, 60, 255)), (0.375, (0, 255, 255)),
        (0.625, (255, 255, 0)), (0.875, (255, 60, 0)), (1.0, (128, 0, 0)),
    ],
}
COLORMAPS = tuple(_ANCHORS)
DEFAULT_COLORMAP = "viridis"


def _build_lut(anchors: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    positions = np.array([p for p, _ in anchors], dtype=np.float64)
    colors = np.array([c for _, c in anchors], dtype=np.float64)
    x = np.linspace(0.0, 1.0, _LEVELS)
    lut = np.empty((_LEVELS, _RGB_CHANNELS), dtype=np.uint8)
    for channel in range(_RGB_CHANNELS):
        lut[:, channel] = np.clip(
            np.rint(np.interp(x, positions, colors[:, channel])), 0, 255).astype(np.uint8)
    return lut


_LUTS = {name: _build_lut(anchors) for name, anchors in _ANCHORS.items()}


def apply_colormap(arr: np.ndarray, name: str = DEFAULT_COLORMAP) -> np.ndarray:
    """Return an HxWx4 RGBA image of *arr* re-coloured through colour map *name*."""
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape}")
    lut = _LUTS.get(name, _LUTS[DEFAULT_COLORMAP])
    luma = np.clip(np.rint(to_luma(arr)), 0, 255).astype(np.int64)
    out = np.empty((*luma.shape, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = lut[luma]
    out[..., 3] = _OPAQUE
    return out
