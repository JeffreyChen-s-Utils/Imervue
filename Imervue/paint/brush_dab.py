"""Dab compositing for the Paint brush engine.

:func:`apply_dab` composites one kernel into an HxWx4 RGBA uint8 canvas at
``(cx, cy)`` with the requested blend mode, :func:`apply_erase_dab` subtracts
it from the alpha, and :func:`dab_bbox` clips a dab against the canvas. Each
returns a :class:`DabResult` damage rect the canvas uses to schedule a partial
repaint.

Re-exported by :mod:`Imervue.paint.brush_engine`, which stays the public
import location.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from Imervue.paint.blend_modes import BLEND_MODES, blend_rgb

# ---------------------------------------------------------------------------
# Dab compositing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DabResult:
    """Damage rectangle (x, y, w, h) describing what changed in the canvas."""

    x: int
    y: int
    w: int
    h: int

    @property
    def is_empty(self) -> bool:
        return self.w <= 0 or self.h <= 0


def apply_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    color: tuple[int, int, int],
    *,
    opacity: float = 1.0,
    blend_mode: str = "normal",
    selection: np.ndarray | None = None,
) -> DabResult:
    """Composite ``kernel * color`` into ``canvas`` at ``(cx, cy)`` in-place.

    ``canvas`` must be HxWx4 uint8 RGBA. Returns the damaged rectangle so
    the caller can schedule a localised repaint.

    The "normal" blend mode takes the integer fixed-point fast path
    (:func:`_composite_normal_u8`) which skips the float32 round-trip
    on the RGB channels and the broadcast-copy of the foreground
    colour — the dominant per-dab cost in the previous numpy
    implementation. Other blend modes fall through to the float32
    path with the foreground passed as a 1-D length-3 array so numpy
    broadcasts at the leaf rather than allocating a full HxWx3 copy.
    """
    _check_canvas(canvas)
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")
    if blend_mode not in BLEND_MODES:
        raise ValueError(
            f"unknown blend_mode {blend_mode!r}; expected one of {BLEND_MODES}",
        )
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return DabResult(0, 0, 0, 0)

    bbox = dab_bbox(canvas.shape[:2], kernel.shape, cx, cy)
    if bbox is None:
        return DabResult(0, 0, 0, 0)
    cx0, cy0, cx1, cy1, kx0, ky0, kx1, ky1 = bbox

    dst_view = canvas[cy0:cy1, cx0:cx1]
    k = kernel[ky0:ky1, kx0:kx1] * opacity   # alpha for this dab
    if selection is not None:
        if selection.shape != canvas.shape[:2]:
            raise ValueError(
                f"selection mask shape {selection.shape} does not match "
                f"canvas {canvas.shape[:2]}",
            )
        k = k * selection[cy0:cy1, cx0:cx1].astype(np.float32)
    if blend_mode == "normal":
        _composite_normal_u8(dst_view, k, color)
    else:
        _composite_in_place(dst_view, k, color, blend_mode)
    return DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0)


def dab_bbox(
    canvas_shape: tuple[int, int],
    kernel_shape: tuple[int, int],
    cx: float,
    cy: float,
) -> tuple[int, int, int, int, int, int, int, int] | None:
    """Clip the kernel placement against the canvas bounds.

    The kernel's origin is ``round(c) - k // 2`` on each axis, so an even
    kernel is biased left / up. Returns ``(cx0, cy0, cx1, cy1, kx0, ky0,
    kx1, ky1)`` — the canvas slice and the matching kernel slice — or
    ``None`` when the dab is fully off-canvas. Every dab-based tool (brush,
    eraser, blur, dodge / burn, sponge, smudge, clone stamp) clips here.
    """
    kh, kw = kernel_shape
    h, w = canvas_shape
    x0 = int(round(cx)) - kw // 2
    y0 = int(round(cy)) - kh // 2
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(w, x0 + kw)
    cy1 = min(h, y0 + kh)
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    return (
        cx0, cy0, cx1, cy1,
        cx0 - x0, cy0 - y0,
        cx0 - x0 + (cx1 - cx0), cy0 - y0 + (cy1 - cy0),
    )


def apply_erase_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    *,
    opacity: float = 1.0,
    selection: np.ndarray | None = None,
) -> DabResult:
    """Subtract ``kernel * opacity`` from ``canvas`` alpha, in-place.

    Eraser semantics — drop alpha by the kernel weight. **Pixels whose
    alpha falls to zero have their RGB channels cleared too**, so a
    later soft-brush stroke that re-touches the erased region doesn't
    pull lingering colour into its anti-aliased edges (which would
    show up as a faint halo of the previously-erased colour, e.g.
    blue ink seeping into a red brush stroke painted over what used
    to be a blue line).

    Pixels whose alpha drops only *partially* (soft eraser, low
    opacity, masked by selection) keep their RGB unchanged — those
    pixels are still partially visible so the existing colour is
    still meaningful. Only the fully-cleared pixels are scrubbed.

    Uses uint8/int32 fixed-point math throughout — no float32
    intermediates. Within ±1 LSB of the float reference and avoids
    the per-dab allocation churn the original implementation paid.
    """
    _check_canvas(canvas)
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return DabResult(0, 0, 0, 0)

    bbox = dab_bbox(canvas.shape[:2], kernel.shape, cx, cy)
    if bbox is None:
        return DabResult(0, 0, 0, 0)
    cx0, cy0, cx1, cy1, kx0, ky0, kx1, ky1 = bbox

    k = kernel[ky0:ky1, kx0:kx1] * opacity
    if selection is not None:
        if selection.shape != canvas.shape[:2]:
            raise ValueError(
                f"selection mask shape {selection.shape} does not match "
                f"canvas {canvas.shape[:2]}",
            )
        k = k * selection[cy0:cy1, cx0:cx1].astype(np.float32)
    # Quantise alpha to int32 0..256 so a >> 8 acts as integer divide.
    a = np.clip((k * 256.0).astype(np.int32, copy=False), 0, 256)
    a8 = canvas[cy0:cy1, cx0:cx1, 3].astype(np.int32)
    a8 -= (a8 * a) >> 8
    np.clip(a8, 0, 255, out=a8)
    canvas[cy0:cy1, cx0:cx1, 3] = a8.astype(np.uint8)
    # Clear RGB on pixels whose alpha just hit zero. The eraser used
    # to leave RGB intact "so a re-paint with the same colour has no
    # halo", but in practice that lingering RGB contaminates soft-
    # brush edges with the colour that *was* there — a stronger bug
    # than the halo it tried to avoid.
    cleared = a8 == 0
    if cleared.any():
        canvas[cy0:cy1, cx0:cx1][cleared, :3] = 0
    return DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0)


def sample_pixel(canvas: np.ndarray, x: float, y: float) -> tuple[int, int, int] | None:
    """Read ``(R, G, B)`` at ``(x, y)`` from the canvas. Returns ``None``
    if the coordinates fall outside the canvas. Used by the eyedropper
    tool to feed ToolState.foreground.
    """
    _check_canvas(canvas)
    h, w = canvas.shape[:2]
    ix = int(round(x))
    iy = int(round(y))
    if not (0 <= ix < w and 0 <= iy < h):
        return None
    pixel = canvas[iy, ix]
    return (int(pixel[0]), int(pixel[1]), int(pixel[2]))


def _composite_normal_u8(
    dst_view: np.ndarray,
    alpha: np.ndarray,
    color: tuple[int, int, int],
) -> None:
    """In-place 'normal' blend without a float32 round-trip.

    Quantises ``alpha`` (float32 in ``[0, 1]``) to int32 ``0..256`` so
    a single ``>> 8`` acts as an integer divide-by-256, then runs
    ``out = bg + ((fg - bg) * alpha) >> 8`` per channel using int32
    math. ``fg`` stays as a length-3 array — numpy broadcasts it
    against the per-pixel ``bg`` instead of allocating a full HxWx3
    copy. Output is within ±1 LSB of the float reference for every
    input combination tested in :mod:`tests.test_paint_brush_engine`.

    Pixels whose ``dst.alpha`` is already zero contribute nothing
    visible, so we substitute ``fg`` for ``bg`` on those pixels
    before mixing. Without this the alpha-over blend would pull the
    lingering RGB of an "erased" pixel into the soft edges of the
    new stroke — the user-visible bug was a colour halo where the
    new brush touched a previously-erased region.
    """
    a = np.clip((alpha * 256.0).astype(np.int32, copy=False), 0, 256)
    fg_arr = np.array(color, dtype=np.int32)
    bg = dst_view[..., :3].astype(np.int32)
    transparent = dst_view[..., 3] == 0
    if transparent.any():
        bg[transparent] = fg_arr
    delta = fg_arr[None, None, :] - bg
    delta *= a[..., None]
    delta >>= 8
    bg += delta
    np.clip(bg, 0, 255, out=bg)
    dst_view[..., :3] = bg.astype(np.uint8)
    a8 = dst_view[..., 3].astype(np.int32)
    a8 += ((256 - a8) * a) >> 8
    np.clip(a8, 0, 255, out=a8)
    dst_view[..., 3] = a8.astype(np.uint8)


def _composite_in_place(
    dst: np.ndarray,
    alpha: np.ndarray,
    color: tuple[int, int, int],
    blend_mode: str,
) -> None:
    """Apply ``alpha``-weighted blend of ``color`` onto the RGBA ``dst``.

    Generic float32 path used for non-``normal`` blend modes. The
    foreground colour is passed as a length-3 sequence and broadcast
    by numpy against the per-pixel background — this skips the
    HxWx3 copy the previous implementation made via
    ``np.broadcast_to(...).copy()``. Mirrors the
    :func:`_composite_normal_u8` rule for fully-transparent
    destination pixels: their lingering RGB has no meaningful
    contribution, so we substitute ``fg`` to keep the soft-edge
    blend free of stale colour.
    """
    bg = dst[..., :3].astype(np.float32) / 255.0
    fg = np.array(color, dtype=np.float32) / 255.0   # shape (3,)
    transparent = dst[..., 3] == 0
    if transparent.any():
        bg[transparent] = fg
    blended = blend_rgb(bg, fg, blend_mode)

    a = alpha[..., None]
    out_rgb = bg * (1.0 - a) + blended * a
    dst[..., :3] = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    dst_a = dst[..., 3].astype(np.float32) / 255.0
    new_a = dst_a + (1.0 - dst_a) * alpha
    dst[..., 3] = np.clip(new_a * 255.0, 0.0, 255.0).astype(np.uint8)


def _union(a: DabResult, b: DabResult) -> DabResult:
    if a.is_empty:
        return b
    if b.is_empty:
        return a
    x0 = min(a.x, b.x)
    y0 = min(a.y, b.y)
    x1 = max(a.x + a.w, b.x + b.w)
    y1 = max(a.y + a.h, b.y + b.h)
    return DabResult(x0, y0, x1 - x0, y1 - y0)


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
