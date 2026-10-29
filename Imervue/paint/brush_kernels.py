"""Brush kernels and dab spacing for the Paint brush engine.

* :func:`round_brush_kernel` / :func:`square_brush_kernel` build the ``(N, N)``
  float32 alpha kernel one dab deposits.
* :func:`spacing_from_brush` and :func:`stroke_dab_positions` decide where the
  dabs of a stroke segment land.
* :func:`_resolve_base_kernel` picks a stroke's base kernel from its options.

Re-exported by :mod:`Imervue.paint.brush_engine`, which stays the public
import location.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Imervue.paint.brush_engine import BrushStrokeOptions

# ---------------------------------------------------------------------------
# Kernel construction
# ---------------------------------------------------------------------------

KERNEL_SIZE_MIN = 1
KERNEL_SIZE_MAX = 1024


def round_brush_kernel(size: int, hardness: float) -> np.ndarray:
    """Return an ``(N, N)`` float32 alpha kernel, normalised to ``[0, 1]``.

    ``hardness`` in ``[0, 1]`` controls the inner-radius plateau:

    * ``hardness == 1`` — fully solid disc (1.0 inside the radius, 0 outside)
    * ``hardness == 0`` — pure radial gradient peaking at the centre
    * intermediate values — solid out to ``hardness * radius`` then a
      smooth-step falloff to the edge

    ``size`` is clamped to :data:`KERNEL_SIZE_MIN`..:data:`KERNEL_SIZE_MAX`
    so callers can pass slider values without re-validating.
    """
    size = max(KERNEL_SIZE_MIN, min(KERNEL_SIZE_MAX, int(size)))
    hardness = max(0.0, min(1.0, float(hardness)))
    if size == 1:
        return np.array([[1.0]], dtype=np.float32)

    radius = (size - 1) / 2.0
    yy, xx = np.indices((size, size), dtype=np.float32)
    cx = cy = radius
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    if hardness >= 1.0:
        kernel = np.where(dist <= radius, 1.0, 0.0)
    else:
        inner = max(0.0, hardness) * radius
        if inner >= radius:
            kernel = np.where(dist <= radius, 1.0, 0.0)
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.clip((dist - inner) / max(1e-6, radius - inner), 0.0, 1.0)
            falloff = 1.0 - (t * t * (3.0 - 2.0 * t))   # smooth-step
            kernel = np.where(dist <= radius, falloff, 0.0)

    return kernel.astype(np.float32, copy=False)


def square_brush_kernel(size: int) -> np.ndarray:
    """Return an ``(N, N)`` float32 kernel with every cell at 1.0.

    The pixel-art kernel: hard square edges, no anti-aliased falloff.
    ``size`` is clamped to the documented brush range.
    """
    size = max(KERNEL_SIZE_MIN, min(KERNEL_SIZE_MAX, int(size)))
    return np.ones((size, size), dtype=np.float32)


# ---------------------------------------------------------------------------
# Stroke interpolation
# ---------------------------------------------------------------------------


def stroke_dab_positions(
    p0: tuple[float, float],
    p1: tuple[float, float],
    spacing: float,
) -> list[tuple[float, float]]:
    """Return dab centres along ``p0 → p1`` at ``spacing`` pixels apart.

    Includes ``p1`` so consecutive segments daisy-chain without gaps.
    Excludes ``p0`` so the caller is in charge of stamping the start
    point exactly once at stroke begin.
    """
    if spacing <= 0:
        raise ValueError(f"spacing must be > 0, got {spacing}")
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx = x1 - x0
    dy = y1 - y0
    distance = float(np.hypot(dx, dy))
    if distance <= spacing:
        return [(x1, y1)]
    n_steps = int(np.ceil(distance / spacing))
    out: list[tuple[float, float]] = []
    for i in range(1, n_steps + 1):
        t = i / n_steps
        out.append((x0 + dx * t, y0 + dy * t))
    return out


def spacing_from_brush(size: int, hardness: float) -> float:
    """full-featured default spacing — small for soft brushes, larger
    for hard brushes. Stays inside [1, size/2] so we always step at
    least one pixel and never skip half a brush.
    """
    size = max(KERNEL_SIZE_MIN, int(size))
    hardness = max(0.0, min(1.0, float(hardness)))
    fraction = 0.10 + 0.30 * (1.0 - hardness)  # softer brush → finer spacing
    return max(1.0, min(size * 0.5, size * fraction))


def _resolve_base_kernel(options: BrushStrokeOptions) -> np.ndarray:
    """Build the per-stroke base kernel — custom tip if set, else round."""
    if options.pixel_art:
        # Pixel-art mode overrides every other kernel choice — hard
        # square with no falloff, regardless of hardness / kind / tip.
        return square_brush_kernel(options.size)
    if options.tip_path:
        try:
            from Imervue.paint.custom_brush import load_brush_tip
            return load_brush_tip(options.tip_path, options.size)
        except (OSError, ValueError):
            # Fall back to the default round kernel; never crash a stroke.
            return round_brush_kernel(options.size, options.hardness)
    return round_brush_kernel(options.size, options.hardness)
