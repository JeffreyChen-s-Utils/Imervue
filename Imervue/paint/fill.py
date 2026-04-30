"""Pure-numpy flood fill for the paint bucket tool.

Two modes:

* contiguous (default) — only fill pixels reachable from the seed
  through 4-connected steps that all stay within the colour-tolerance
  band. The classic paint-bucket behaviour.
* global — fill every pixel that matches the seed within tolerance,
  regardless of connectivity. MediBang's "all matching pixels" mode.

Tolerance is the maximum per-channel absolute RGB difference allowed
versus the seed. ``tolerance=0`` requires an exact match; ``tolerance=255``
matches everything. Alpha is ignored when computing matches and is
always written full-opaque on filled pixels (otherwise the bucket
would deposit translucent paint that's a foot-gun to debug).

The contiguous flood uses iterative 4-connectivity dilation against
a precomputed candidate mask. This is vectorised so it stays fast on
large canvases without scipy as a dependency. Worst-case iterations
are bounded by the canvas diameter; typical fills converge in tens of
passes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FillResult:
    """Damage rect describing which pixels the fill changed."""

    x: int
    y: int
    w: int
    h: int
    pixels_filled: int

    @property
    def is_empty(self) -> bool:
        return self.pixels_filled <= 0


def flood_fill(
    canvas: np.ndarray,
    seed_x: int,
    seed_y: int,
    color: tuple[int, int, int],
    *,
    tolerance: int = 32,
    contiguous: bool = True,
    selection: np.ndarray | None = None,
) -> FillResult:
    """Fill the region around ``(seed_x, seed_y)`` with ``color``.

    If ``selection`` is provided (HxW bool mask), the fill is clipped
    to the selection — pixels outside it are never modified, even when
    they fall inside the colour-tolerance band.
    """
    _check_canvas(canvas)
    h, w = canvas.shape[:2]
    sx, sy = int(round(seed_x)), int(round(seed_y))
    if not (0 <= sx < w and 0 <= sy < h):
        return FillResult(0, 0, 0, 0, 0)
    if selection is not None:
        if selection.shape != (h, w):
            raise ValueError(
                f"selection mask shape {selection.shape} does not match "
                f"canvas {(h, w)}",
            )
        if not selection[sy, sx]:
            # Seed lies outside the selection — fill never starts.
            return FillResult(0, 0, 0, 0, 0)
    tolerance = max(0, min(255, int(tolerance)))

    seed = canvas[sy, sx, :3].astype(np.int16)
    diff = np.abs(canvas[..., :3].astype(np.int16) - seed[None, None, :])
    candidates = diff.max(axis=-1) <= tolerance
    if selection is not None:
        candidates = candidates & selection

    mask = _contiguous_region(candidates, sx, sy) if contiguous else candidates

    pixels_filled = int(mask.sum())
    if pixels_filled == 0:
        return FillResult(0, 0, 0, 0, 0)

    canvas[mask, 0] = int(color[0])
    canvas[mask, 1] = int(color[1])
    canvas[mask, 2] = int(color[2])
    canvas[mask, 3] = 255

    ys, xs = np.where(mask)
    return FillResult(
        int(xs.min()), int(ys.min()),
        int(xs.max() - xs.min() + 1),
        int(ys.max() - ys.min() + 1),
        pixels_filled,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _contiguous_region(candidates: np.ndarray, sx: int, sy: int) -> np.ndarray:
    """Iterative 4-connected dilation from the seed, clipped by candidates."""
    if not candidates[sy, sx]:
        return np.zeros_like(candidates)

    mask = np.zeros_like(candidates)
    mask[sy, sx] = True
    while True:
        # Shift the mask in every direction and OR with the original.
        # Using `np.pad`-based shifts (not `np.roll`) so wrap-around
        # doesn't bleed across the canvas edges.
        shifted_up = np.zeros_like(mask)
        shifted_up[:-1, :] = mask[1:, :]
        shifted_down = np.zeros_like(mask)
        shifted_down[1:, :] = mask[:-1, :]
        shifted_left = np.zeros_like(mask)
        shifted_left[:, :-1] = mask[:, 1:]
        shifted_right = np.zeros_like(mask)
        shifted_right[:, 1:] = mask[:, :-1]

        expanded = mask | shifted_up | shifted_down | shifted_left | shifted_right
        new_mask = expanded & candidates
        if new_mask.sum() == mask.sum():
            return mask
        mask = new_mask


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"flood_fill expects HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
