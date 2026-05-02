"""Smudge / mixer brush — drag canvas pixels along the stroke path.

On press, the tool snapshots the canvas pixels currently under the
brush footprint into a "carried" buffer. On move, every interpolated
dab blends ``carried`` into the canvas (weighted by the brush kernel
and the strength slider), then mixes a fraction of the new canvas
content back into ``carried``. The net effect is that pigment
appears to slide along the cursor path.

Pure numpy. Kept Qt-free so it can be tested without a display
server. The dispatcher (:class:`Imervue.paint.tool_dispatcher.SmudgeTool`)
manages the per-stroke state and feeds positions through the same
``stroke_dab_positions`` interpolator the brush engine uses.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.brush_engine import DabResult

STRENGTH_MIN = 0.0
STRENGTH_MAX = 1.0
DECAY_MIN = 0.0
DECAY_MAX = 1.0


def sample_carry(
    canvas: np.ndarray, cx: float, cy: float, kernel: np.ndarray,
) -> np.ndarray:
    """Snapshot the canvas pixels under the brush footprint.

    Returns an HxWx4 uint8 buffer the same shape as ``kernel``,
    extracted from the canvas at the dab centre with edge clipping.
    Pixels outside the canvas are zero-filled.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")

    kh, kw = kernel.shape
    half_w = kw // 2
    half_h = kh // 2
    x0 = int(round(cx)) - half_w
    y0 = int(round(cy)) - half_h
    out = np.zeros((kh, kw, 4), dtype=np.uint8)

    h, w = canvas.shape[:2]
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(w, x0 + kw)
    cy1 = min(h, y0 + kh)
    if cx1 <= cx0 or cy1 <= cy0:
        return out

    out[
        cy0 - y0: cy1 - y0,
        cx0 - x0: cx1 - x0,
    ] = canvas[cy0:cy1, cx0:cx1]
    return out


def smudge_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    carried: np.ndarray,
    *,
    strength: float = 0.6,
    decay: float = 0.7,
    selection: np.ndarray | None = None,
) -> tuple[DabResult, np.ndarray]:
    """Apply one smudge dab, returning the damage rect + updated carry buffer.

    ``strength`` controls how much of the carried colour bleeds into
    the canvas (0 = no smear, 1 = paint replaced by carry). ``decay``
    controls how fast carried picks up new canvas content (0 =
    carried never updates, 1 = carried always equals canvas).
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")
    if carried.shape != (*kernel.shape, 4) or carried.dtype != np.uint8:
        raise ValueError(
            f"carried buffer shape {carried.shape} must match kernel "
            f"with 4 channels (uint8)",
        )
    strength = max(STRENGTH_MIN, min(STRENGTH_MAX, float(strength)))
    decay = max(DECAY_MIN, min(DECAY_MAX, float(decay)))

    kh, kw = kernel.shape
    half_w = kw // 2
    half_h = kh // 2
    x0 = int(round(cx)) - half_w
    y0 = int(round(cy)) - half_h

    h, w = canvas.shape[:2]
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(w, x0 + kw)
    cy1 = min(h, y0 + kh)
    if cx1 <= cx0 or cy1 <= cy0:
        return (DabResult(0, 0, 0, 0), carried)

    kx0 = cx0 - x0
    ky0 = cy0 - y0
    kx1 = kx0 + (cx1 - cx0)
    ky1 = ky0 + (cy1 - cy0)

    k = kernel[ky0:ky1, kx0:kx1].astype(np.float32) * strength
    if selection is not None:
        if selection.shape != canvas.shape[:2]:
            raise ValueError(
                f"selection shape {selection.shape} does not match canvas "
                f"{canvas.shape[:2]}",
            )
        k = k * selection[cy0:cy1, cx0:cx1].astype(np.float32)

    dst = canvas[cy0:cy1, cx0:cx1]
    src_carry = carried[ky0:ky1, kx0:kx1]
    dst_f = dst.astype(np.float32)
    carry_f = src_carry.astype(np.float32)
    blend = dst_f + (carry_f - dst_f) * k[..., None]
    canvas[cy0:cy1, cx0:cx1] = np.clip(blend, 0.0, 255.0).astype(np.uint8)

    # Update carry — pick up a fraction of the new canvas content so
    # the colour shifts as you drag across different regions.
    new_carry = carried.copy()
    new_canvas = canvas[cy0:cy1, cx0:cx1].astype(np.float32)
    blended_carry = (
        carry_f * (1.0 - decay) + new_canvas * decay
    )
    new_carry[ky0:ky1, kx0:kx1] = np.clip(
        blended_carry, 0.0, 255.0,
    ).astype(np.uint8)

    return (
        DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0),
        new_carry,
    )
