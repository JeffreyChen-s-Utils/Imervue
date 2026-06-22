"""Dodge & burn dab — selectively lighten or darken under the brush.

The dodge and burn tools are brush-style mutators: each pointer dab nudges
the canvas toward white (dodge) or black (burn), weighted by the brush
kernel's alpha and a tonal-range mask so the adjustment concentrates on
shadows, midtones or highlights the way the darkroom tools do. Pure
numpy so the dispatcher can call it on every pointer move without dragging
in OpenCV at import time.
"""
from __future__ import annotations

import numpy as np

_MAX_BYTE = 255.0
# Rec.709 luminance weights — used to pick the tonal band a dab targets.
_LUMA_R, _LUMA_G, _LUMA_B = 0.2126, 0.7152, 0.0722
# Tonal ranges a dab can bias toward, mirroring the darkroom tools.
TONAL_RANGES = ("shadows", "midtones", "highlights")


def _validate_range(range_mode: str) -> None:
    """Raise ``ValueError`` unless ``range_mode`` names a known tonal band."""
    if range_mode not in TONAL_RANGES:
        raise ValueError(
            f"range_mode must be one of {TONAL_RANGES}, got {range_mode!r}",
        )


def _tonal_weight(luma: np.ndarray, range_mode: str) -> np.ndarray:
    """Per-pixel weight in ``[0, 1]`` selecting the targeted tonal band.

    ``luma`` is normalised to ``[0, 1]``. Shadows peak at black, highlights
    at white, and midtones form a tent peaking at mid-grey. ``range_mode``
    is assumed pre-validated by :func:`_validate_range`.
    """
    if range_mode == "shadows":
        return 1.0 - luma
    if range_mode == "highlights":
        return luma
    return 1.0 - np.abs(2.0 * luma - 1.0)  # midtones


def dodge_burn_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    *,
    amount: float,
    range_mode: str = "midtones",
    selection: np.ndarray | None = None,
) -> tuple[int, int, int, int]:
    """Apply one dodge/burn dab centred on ``(cx, cy)``.

    ``amount`` > 0 dodges (lightens toward white), < 0 burns (darkens
    toward black); its magnitude is the strength, clamped to ``[0, 1]``.
    ``range_mode`` selects which tonal band the dab concentrates on.

    Returns the damage rect ``(x, y, w, h)`` of the patch that actually
    changed so the canvas can do a sub-region GPU upload. Empty rect when
    the dab fell off-canvas or ``amount`` rounded to zero.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"dodge_burn_dab expects HxWx4 uint8 RGBA, got "
            f"{canvas.shape} {canvas.dtype}",
        )
    _validate_range(range_mode)
    amount = float(max(-1.0, min(1.0, amount)))
    if not amount:  # clamped to [-1, 1]; only an exact zero is a no-op
        return (0, 0, 0, 0)
    h, w = canvas.shape[:2]
    kh, kw = kernel.shape
    # ``apply_dab`` convention: origin = round(c) - k//2 spans [origin,
    # origin + k). Even-sized kernels bias left/top (matches brush engine).
    x0_full = int(round(cx)) - kw // 2
    y0_full = int(round(cy)) - kh // 2
    x0 = max(0, x0_full)
    y0 = max(0, y0_full)
    x1 = min(w, x0_full + kw)
    y1 = min(h, y0_full + kh)
    if x1 <= x0 or y1 <= y0:
        return (0, 0, 0, 0)

    # Kernel slice that lines up with the clipped patch.
    kx0 = x0 - x0_full
    ky0 = y0 - y0_full
    kx1 = kx0 + (x1 - x0)
    ky1 = ky0 + (y1 - y0)
    patch = canvas[y0:y1, x0:x1, :3].astype(np.float32) / _MAX_BYTE
    kernel_slice = np.clip(kernel[ky0:ky1, kx0:kx1].astype(np.float32), 0.0, 1.0)
    luma = (
        _LUMA_R * patch[..., 0]
        + _LUMA_G * patch[..., 1]
        + _LUMA_B * patch[..., 2]
    )
    weight = kernel_slice * _tonal_weight(luma, range_mode) * abs(amount)
    if selection is not None:
        sel_slice = np.clip(
            selection[y0:y1, x0:x1].astype(np.float32), 0.0, 1.0,
        )
        weight = weight * sel_slice
    # Move each pixel a fraction of the way to white (dodge) or black
    # (burn). The headroom factor keeps the result monotonic and bounded:
    # white can't dodge brighter, black can't burn darker.
    if amount > 0:
        patch += weight[..., None] * (1.0 - patch)
    else:
        patch -= weight[..., None] * patch
    np.clip(patch, 0.0, 1.0, out=patch)
    canvas[y0:y1, x0:x1, :3] = (patch * _MAX_BYTE + 0.5).astype(np.uint8)
    return (x0, y0, x1 - x0, y1 - y0)
