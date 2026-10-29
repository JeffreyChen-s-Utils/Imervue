"""Two-buffer layer compositing: one RGBA layer over another.

Combines two HxWx4 uint8 RGBA buffers (each with its own alpha channel)
through one of the shared blend modes, with layer opacity and an optional
layer mask. :mod:`Imervue.paint.compositing` walks the layer stack and
calls :func:`composite_layer_pair` once per visible layer; it re-exports
every public name here.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.blend_modes import BLEND_MODES, blend_rgb

# Re-exported under the layer-compositing name; the canonical tuple lives in
# blend_modes so the brush engine and the compositor can't drift apart.
LAYER_BLEND_MODES = BLEND_MODES

# Guards the un-premultiply division where the composited alpha is zero
# (both inputs fully transparent — the premultiplied numerator is zero
# there too, so the quotient stays 0 rather than NaN).
_ALPHA_EPS = 1e-6


def composite_layer_pair(
    below: np.ndarray,
    above: np.ndarray,
    *,
    opacity: float = 1.0,
    blend_mode: str = "normal",
    mask: np.ndarray | None = None,
) -> np.ndarray:
    """Place ``above`` over ``below`` using ``blend_mode`` and ``opacity``.

    Both inputs must be HxWx4 uint8 RGBA of the same shape. ``mask`` is
    an optional ``HxW`` uint8 alpha buffer that further attenuates the
    above layer (used by layer masks).
    """
    _check_pair(below, above)
    if blend_mode not in LAYER_BLEND_MODES:
        raise ValueError(
            f"unknown blend_mode {blend_mode!r}; expected one of {LAYER_BLEND_MODES}",
        )
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return below.copy()

    h, w = below.shape[:2]
    if mask is not None:
        if mask.shape != (h, w):
            raise ValueError(
                f"mask shape {mask.shape} does not match canvas {(h, w)}",
            )
        if mask.dtype != np.uint8:
            raise ValueError(f"mask dtype must be uint8, got {mask.dtype}")

    bg_rgb = below[..., :3].astype(np.float32) / 255.0
    bg_a = below[..., 3].astype(np.float32) / 255.0
    fg_rgb = above[..., :3].astype(np.float32) / 255.0
    fg_a = above[..., 3].astype(np.float32) / 255.0
    fg_a = fg_a * opacity
    if mask is not None:
        fg_a = fg_a * (mask.astype(np.float32) / 255.0)

    blended_rgb = blend_rgb(bg_rgb, fg_rgb, blend_mode)
    # Blend modes are defined against the backdrop colour; where the
    # backdrop is (partially) transparent there is no colour to blend
    # with, so the blended result fades toward the raw foreground.
    blended_rgb = (
        fg_rgb * (1.0 - bg_a)[..., None] + blended_rgb * bg_a[..., None]
    )
    out_a = fg_a + bg_a * (1.0 - fg_a)
    # Straight-alpha "over": weight each colour by its coverage, then
    # un-premultiply. Every layer buffer and the GL display path use the
    # straight-alpha convention; without the division, a semi-transparent
    # pixel over a transparent backdrop comes out premultiplied
    # (rgb * alpha) and darkens on every merge / flatten / region patch.
    premul_rgb = (
        blended_rgb * fg_a[..., None]
        + bg_rgb * (bg_a * (1.0 - fg_a))[..., None]
    )
    out_rgb = premul_rgb / np.maximum(out_a, _ALPHA_EPS)[..., None]

    out = np.empty_like(below)
    out[..., :3] = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    out[..., 3] = np.clip(out_a * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Internals — same blend curves as the brush engine, vectorised here.
# ---------------------------------------------------------------------------


def _check_pair(below: np.ndarray, above: np.ndarray) -> None:
    if below.ndim != 3 or below.shape[2] != 4 or below.dtype != np.uint8:
        raise ValueError(f"below must be HxWx4 uint8 RGBA, got {below.shape} {below.dtype}")
    if above.shape != below.shape or above.dtype != np.uint8:
        raise ValueError(
            f"above must match below shape/dtype: got {above.shape} {above.dtype} "
            f"vs {below.shape} {below.dtype}",
        )
