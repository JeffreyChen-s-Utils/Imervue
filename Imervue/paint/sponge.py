"""Sponge dab — locally saturate or desaturate under the brush.

The sponge is the third darkroom-toning brush alongside dodge and burn:
each pointer dab scales the canvas's chroma toward grey (desaturate) or
away from it (saturate), weighted by the brush kernel's alpha. The pivot
is the Rec.709 luminance, so desaturating preserves perceived brightness
exactly. Pure numpy so the dispatcher can call it on every pointer move
without dragging in OpenCV at import time.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.brush_engine import dab_bbox

_MAX_BYTE = 255.0
# Rec.709 luminance weights — the neutral pivot chroma is scaled around.
_LUMA_R, _LUMA_G, _LUMA_B = 0.2126, 0.7152, 0.0722


def sponge_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    *,
    amount: float,
    selection: np.ndarray | None = None,
) -> tuple[int, int, int, int]:
    """Apply one sponge dab centred on ``(cx, cy)``.

    ``amount`` > 0 saturates (pushes chroma away from grey), < 0
    desaturates (pulls it toward grey); its magnitude is the strength,
    clamped to ``[0, 1]``. Returns the damage rect ``(x, y, w, h)`` of the
    patch that actually changed so the canvas can do a sub-region GPU
    upload. Empty rect when the dab fell off-canvas or ``amount`` was zero.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"sponge_dab expects HxWx4 uint8 RGBA, got "
            f"{canvas.shape} {canvas.dtype}",
        )
    amount = float(max(-1.0, min(1.0, amount)))
    if not amount:  # clamped to [-1, 1]; only an exact zero is a no-op
        return (0, 0, 0, 0)
    bbox = dab_bbox(canvas.shape[:2], kernel.shape, cx, cy)
    if bbox is None:
        return (0, 0, 0, 0)
    x0, y0, x1, y1, kx0, ky0, kx1, ky1 = bbox
    patch = canvas[y0:y1, x0:x1, :3].astype(np.float32) / _MAX_BYTE
    kernel_slice = np.clip(kernel[ky0:ky1, kx0:kx1].astype(np.float32), 0.0, 1.0)
    weight = kernel_slice
    if selection is not None:
        weight = weight * np.clip(
            selection[y0:y1, x0:x1].astype(np.float32), 0.0, 1.0,
        )
    grey = (
        _LUMA_R * patch[..., 0]
        + _LUMA_G * patch[..., 1]
        + _LUMA_B * patch[..., 2]
    )[..., None]
    # factor < 1 pulls chroma toward grey, > 1 pushes it away; pivoting on
    # luminance keeps perceived brightness fixed while desaturating.
    factor = (1.0 + amount * weight)[..., None]
    patch = grey + (patch - grey) * factor
    np.clip(patch, 0.0, 1.0, out=patch)
    canvas[y0:y1, x0:x1, :3] = (patch * _MAX_BYTE + 0.5).astype(np.uint8)
    return (x0, y0, x1 - x0, y1 - y0)
