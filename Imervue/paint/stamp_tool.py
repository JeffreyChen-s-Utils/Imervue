"""Clone-stamp tool — copy a region of the canvas via brush stamps.

Workflow mirrors Photoshop / raster paint apps's stamp tool:

1. Alt-click on the canvas to set the source point.
2. Subsequent strokes paint pixels copied from the source area
   (offset by the difference between the click point and the
   source point).
3. A new Alt-click resets the source.

Pure-numpy / Qt-free: this module owns the state machine + dab
verb. The :mod:`tool_dispatcher` integration adds the keyboard
modifier handling.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from Imervue.paint.brush_engine import round_brush_kernel
from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.damage import DamageRect

DEFAULT_STAMP_SIZE = 24
DEFAULT_STAMP_HARDNESS = 0.6
DEFAULT_STAMP_OPACITY = 1.0


@dataclass
class StampState:
    """Per-stroke clone-stamp state.

    Tracks the source point (the user's Alt-click) plus a per-stroke
    delta — the offset from the first dab in the current stroke to
    the source. That delta determines which canvas pixels each
    subsequent dab samples. A new stroke (after a release) keeps
    the same source but starts a fresh delta from its first dab.
    """

    source: tuple[float, float] | None = None
    stroke_anchor: tuple[float, float] | None = None

    def has_source(self) -> bool:
        return self.source is not None

    def set_source(self, point: tuple[float, float]) -> None:
        self.source = (float(point[0]), float(point[1]))
        # Force a fresh stroke offset on the next dab.
        self.stroke_anchor = None

    def begin_stroke(self, dab_position: tuple[float, float]) -> None:
        """Mark the first dab of a new stroke; later dabs sample
        relative to this anchor."""
        self.stroke_anchor = (float(dab_position[0]), float(dab_position[1]))

    def end_stroke(self) -> None:
        self.stroke_anchor = None

    def offset_for(
        self, dab_position: tuple[float, float],
    ) -> tuple[float, float] | None:
        """Return the (dx, dy) from ``dab_position`` to the matching
        source pixel, or ``None`` if no source / stroke anchor is set."""
        if self.source is None or self.stroke_anchor is None:
            return None
        return (
            self.source[0] + (dab_position[0] - self.stroke_anchor[0]),
            self.source[1] + (dab_position[1] - self.stroke_anchor[1]),
        )


def stamp_dab(
    canvas: np.ndarray,
    state: StampState,
    cx: float,
    cy: float,
    *,
    size: int = DEFAULT_STAMP_SIZE,
    hardness: float = DEFAULT_STAMP_HARDNESS,
    opacity: float = DEFAULT_STAMP_OPACITY,
) -> DamageRect:
    """Stamp pixels from the source region under the brush footprint.

    Sampling uses nearest-neighbour for simplicity — bilinear would
    soften edges but the stamp tool's mental model is "copy these
    pixels", not "interpolate them". The brush kernel modulates the
    alpha so the user can fade-out the cloned region by holding the
    stroke at a single point.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    if state.source is None:
        return EMPTY_DAMAGE
    if state.stroke_anchor is None:
        # First dab of the stroke; pin the anchor here.
        state.begin_stroke((cx, cy))
    if not 0.0 <= float(opacity) <= 1.0:
        raise ValueError(f"opacity must be in [0, 1], got {opacity!r}")
    if opacity <= 0.0:
        return EMPTY_DAMAGE

    kernel = round_brush_kernel(size, hardness)
    kh, kw = kernel.shape
    half_w = kw // 2
    half_h = kh // 2
    dst_x0 = int(round(cx)) - half_w
    dst_y0 = int(round(cy)) - half_h
    dst_x1 = dst_x0 + kw
    dst_y1 = dst_y0 + kh

    h, w = canvas.shape[:2]
    cx0 = max(0, dst_x0)
    cy0 = max(0, dst_y0)
    cx1 = min(w, dst_x1)
    cy1 = min(h, dst_y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return EMPTY_DAMAGE

    src_offset_x, src_offset_y = state.offset_for((cx, cy))
    # Build the source-coordinate grid for every destination pixel.
    src_origin_x = src_offset_x - half_w
    src_origin_y = src_offset_y - half_h
    src_xs = np.arange(cx0 - dst_x0, cx1 - dst_x0) + int(round(src_origin_x))
    src_ys = np.arange(cy0 - dst_y0, cy1 - dst_y0) + int(round(src_origin_y))
    in_bounds_x = (src_xs >= 0) & (src_xs < w)
    in_bounds_y = (src_ys >= 0) & (src_ys < h)
    if not in_bounds_x.any() or not in_bounds_y.any():
        return EMPTY_DAMAGE

    valid_xs = np.clip(src_xs, 0, w - 1)
    valid_ys = np.clip(src_ys, 0, h - 1)
    source_patch = canvas[
        valid_ys[:, None], valid_xs[None, :], :
    ].astype(np.float32) / 255.0

    kernel_slice = kernel[
        cy0 - dst_y0:cy1 - dst_y0,
        cx0 - dst_x0:cx1 - dst_x0,
    ] * float(opacity)
    # Pixels whose source sample is out-of-bounds contribute zero alpha.
    valid_grid = (
        in_bounds_y[:cy1 - cy0][:, None] & in_bounds_x[:cx1 - cx0][None, :]
    )
    kernel_slice = kernel_slice * valid_grid.astype(np.float32)
    if not np.any(kernel_slice > 0):
        return EMPTY_DAMAGE

    dst_view = canvas[cy0:cy1, cx0:cx1, :]
    bg = dst_view.astype(np.float32) / 255.0
    a = kernel_slice[..., None]
    out = bg[..., :3] * (1.0 - a) + source_patch[..., :3] * a
    dst_view[..., :3] = np.clip(out * 255.0, 0.0, 255.0).astype(np.uint8)
    new_alpha = bg[..., 3] + (1.0 - bg[..., 3]) * kernel_slice
    dst_view[..., 3] = np.clip(new_alpha * 255.0, 0.0, 255.0).astype(np.uint8)
    return DamageRect(x=cx0, y=cy0, w=cx1 - cx0, h=cy1 - cy0)
