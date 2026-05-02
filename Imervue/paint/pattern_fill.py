"""Tile a small pattern image across a canvas region.

Pure-numpy + Pillow (for the optional scale / rotate steps): stamp a
seamless pattern across an HxWx4 RGBA canvas with configurable
offset, uniform scale, rotation, and per-fill opacity. Selection
masks clip the result to the active region. Useful for both the
fill-with-pattern command and as the basis for a future pattern
brush (each dab samples from a tiled pattern instead of a flat
colour).

Pattern textures are typically small (32×32 .. 512×512); scaling /
rotating happens once per call rather than per dab so the cost
amortises across the whole fill region.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

from Imervue.paint.compositing import composite_layer_pair

MIN_SCALE = 0.05
MAX_SCALE = 32.0


def render_pattern_fill(
    canvas: np.ndarray,
    pattern: np.ndarray,
    *,
    offset: tuple[int, int] = (0, 0),
    scale: float = 1.0,
    rotation_deg: float = 0.0,
    opacity: float = 1.0,
    selection: np.ndarray | None = None,
) -> bool:
    """Tile ``pattern`` across ``canvas`` with the supplied transform.

    Both inputs must be HxWx4 uint8 RGBA. ``offset`` shifts the
    tiling origin, ``scale`` (in ``[0.05, 32]``) resizes the pattern
    before tiling, ``rotation_deg`` rotates it (counter-clockwise),
    ``opacity`` scales the composited alpha, ``selection`` (HxW
    bool, optional) clips the fill to the active region.

    Returns ``True`` if any pixel actually changed.
    """
    _check_rgba(canvas, name="canvas")
    _check_rgba(pattern, name="pattern")
    if not MIN_SCALE <= float(scale) <= MAX_SCALE:
        raise ValueError(
            f"scale must be in [{MIN_SCALE}, {MAX_SCALE}], got {scale!r}",
        )
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return False

    pat = _transform_pattern(pattern, scale, rotation_deg)
    ph, pw = pat.shape[:2]
    if ph == 0 or pw == 0:
        return False

    h, w = canvas.shape[:2]
    if selection is not None:
        if selection.shape != (h, w):
            raise ValueError(
                f"selection shape {selection.shape} does not match "
                f"canvas {(h, w)}",
            )
        if selection.dtype != np.bool_:
            raise ValueError(
                f"selection must be bool, got {selection.dtype}",
            )
        if not selection.any():
            return False

    ox, oy = int(offset[0]), int(offset[1])
    ys, xs = np.indices((h, w))
    px = (xs - ox) % pw
    py = (ys - oy) % ph
    tiled = pat[py, px]

    mask_u8 = None
    if selection is not None:
        mask_u8 = np.where(selection, 255, 0).astype(np.uint8)

    blended = composite_layer_pair(
        canvas, tiled,
        opacity=opacity,
        blend_mode="normal",
        mask=mask_u8,
    )
    np.copyto(canvas, blended)
    return True


def _transform_pattern(
    pattern: np.ndarray, scale: float, rotation_deg: float,
) -> np.ndarray:
    """Apply scale + rotation to the pattern via Pillow.

    Identity transforms (scale == 1, rotation == 0) skip the round
    through Pillow so the common case stays cheap. ``isclose`` is
    used so a slider that lands a hair off integer 1.0 / 0.0 still
    short-circuits rather than burning a Pillow round-trip."""
    if math.isclose(scale, 1.0) and math.isclose(rotation_deg, 0.0):
        return pattern
    pil = Image.fromarray(pattern, mode="RGBA")
    if not math.isclose(scale, 1.0):
        ph, pw = pattern.shape[:2]
        new_w = max(1, int(round(pw * scale)))
        new_h = max(1, int(round(ph * scale)))
        # NEAREST preserves crisp edges in pixel-art / checker patterns;
        # bilinear would smear black/white boundaries in a 2× checker
        # into 64-grey transition pixels. Soft-texture callers can wrap
        # this and pre-blur if they want smooth scaling.
        pil = pil.resize((new_w, new_h), Image.NEAREST)
    if not math.isclose(rotation_deg, 0.0):
        pil = pil.rotate(
            float(rotation_deg), resample=Image.BILINEAR, expand=False,
        )
    return np.asarray(pil)


def _check_rgba(image: np.ndarray, *, name: str) -> None:
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"{name} must be HxWx4 uint8 RGBA, got "
            f"{image.shape} {image.dtype}",
        )
