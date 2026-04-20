"""Split toning — apply distinct colour tints to shadows and highlights.

The result is the canonical Lightroom-style split tone: a luminance-weighted
blend between a shadow tint and a highlight tint with a balance slider to
pivot which luminance range receives which tint.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("Imervue.split_toning")

_MAX_SATURATION = 1.0
_BALANCE_SCALE = 0.5   # maps -1..+1 to -0.5..+0.5 luminance shift


def _hsl_to_rgb(hue_deg: float, sat: float) -> np.ndarray:
    """Return an RGB tint (float32, 0..1) at lightness = 0.5."""
    import colorsys
    r, g, b = colorsys.hls_to_rgb((hue_deg % 360.0) / 360.0, 0.5, sat)
    return np.array([r, g, b], dtype=np.float32)


def apply_split_toning(
    arr: np.ndarray,
    shadow_hue: float = 210.0,
    shadow_saturation: float = 0.0,
    highlight_hue: float = 45.0,
    highlight_saturation: float = 0.0,
    balance: float = 0.0,
) -> np.ndarray:
    """Blend in shadow/highlight tints weighted by luminance.

    *balance* in ``[-1, +1]``: negative shifts split-point toward shadows
    (more area gets the highlight tint), positive shifts toward highlights.
    Saturations in ``[0, 1]``.
    """
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_split_toning expects HxWx4 RGBA uint8")
    shadow_saturation = max(0.0, min(_MAX_SATURATION, float(shadow_saturation)))
    highlight_saturation = max(0.0, min(_MAX_SATURATION, float(highlight_saturation)))
    if shadow_saturation < 1e-4 and highlight_saturation < 1e-4:
        return arr

    rgb = arr[..., :3].astype(np.float32) / 255.0
    # Rec. 709 luminance for the shadow/highlight weight.
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    pivot = 0.5 + _BALANCE_SCALE * float(balance)
    pivot = float(np.clip(pivot, 0.05, 0.95))
    highlight_w = np.clip((luma - pivot) / (1.0 - pivot), 0.0, 1.0)
    shadow_w = np.clip((pivot - luma) / pivot, 0.0, 1.0)

    shadow_tint = _hsl_to_rgb(shadow_hue, shadow_saturation)
    highlight_tint = _hsl_to_rgb(highlight_hue, highlight_saturation)

    # Soft-light style blend: tint * 2 - 1 added proportionally.
    sh_delta = (shadow_tint - 0.5)[None, None, :] * shadow_w[..., None] \
        * (2.0 * shadow_saturation)
    hi_delta = (highlight_tint - 0.5)[None, None, :] * highlight_w[..., None] \
        * (2.0 * highlight_saturation)
    toned = np.clip(rgb + sh_delta + hi_delta, 0.0, 1.0)

    out = arr.copy()
    out[..., :3] = (toned * 255.0 + 0.5).astype(np.uint8)
    return out
