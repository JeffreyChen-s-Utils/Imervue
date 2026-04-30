"""Selection mask helpers for the paint workspace.

Selections are HxW boolean numpy arrays — ``True`` means "pixel is part
of the active selection". Combination modes ('replace' / 'add' /
'subtract' / 'intersect') mirror MediBang's selection-modifier strip.

The pure-logic primitives here are Qt-free so the selection-tool
dispatchers can be unit-tested without a display server.
"""
from __future__ import annotations

import numpy as np

SELECTION_MODES = ("replace", "add", "subtract", "intersect")
DEFAULT_SELECTION_MODE = "replace"


def combine(
    existing: np.ndarray | None,
    new: np.ndarray,
    mode: str,
) -> np.ndarray:
    """Combine ``new`` into ``existing`` according to ``mode``.

    ``existing`` may be ``None`` (no prior selection) — in that case
    only "replace" and "add" produce a non-empty result; "subtract"
    and "intersect" return an all-False mask of the right shape.
    """
    if mode not in SELECTION_MODES:
        raise ValueError(
            f"unknown selection mode {mode!r}; expected one of {SELECTION_MODES}",
        )
    if new.dtype != np.bool_:
        raise ValueError(f"new selection must be bool, got {new.dtype}")
    if existing is None:
        if mode in ("replace", "add"):
            return new.copy()
        return np.zeros_like(new)
    if existing.shape != new.shape:
        raise ValueError(
            f"selection shapes mismatch: existing {existing.shape}, new {new.shape}",
        )
    if mode == "replace":
        return new.copy()
    if mode == "add":
        return existing | new
    if mode == "subtract":
        return existing & ~new
    return existing & new   # intersect


def rectangle_mask(
    h: int, w: int, x0: int, y0: int, x1: int, y1: int,
) -> np.ndarray:
    """Return a boolean mask covering the given rectangle.

    Coordinates are clamped into ``[0, h)`` / ``[0, w)`` and
    automatically swapped if the user dragged from bottom-right to
    top-left.
    """
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas dimensions must be positive, got {h}x{w}")
    lo_x = max(0, min(w - 1, x0, x1))
    hi_x = max(0, min(w - 1, max(x0, x1)))
    lo_y = max(0, min(h - 1, y0, y1))
    hi_y = max(0, min(h - 1, max(y0, y1)))
    mask = np.zeros((h, w), dtype=np.bool_)
    mask[lo_y:hi_y + 1, lo_x:hi_x + 1] = True
    return mask


def polygon_mask(h: int, w: int, points: list[tuple[float, float]]) -> np.ndarray:
    """Return a boolean mask filled by the polygon defined by ``points``.

    Uses the standard even-odd fill rule. Self-intersecting polygons
    therefore have alternating filled / hole regions, matching Photoshop
    and MediBang's lasso behaviour.
    """
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas dimensions must be positive, got {h}x{w}")
    mask = np.zeros((h, w), dtype=np.bool_)
    if len(points) < 3:
        return mask

    n = len(points)
    for y in range(h):
        crossings: list[float] = []
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                # Linear interpolation: x at scanline y.
                t = (y - y0) / (y1 - y0)
                crossings.append(x0 + t * (x1 - x0))
        crossings.sort()
        for i in range(0, len(crossings), 2):
            if i + 1 >= len(crossings):
                break
            lo = max(0, int(np.ceil(crossings[i])))
            hi = min(w, int(np.floor(crossings[i + 1])) + 1)
            if hi > lo:
                mask[y, lo:hi] = True
    return mask


def magic_wand_mask(
    canvas: np.ndarray,
    seed_x: int,
    seed_y: int,
    *,
    tolerance: int = 32,
    contiguous: bool = True,
) -> np.ndarray:
    """Return a boolean mask of pixels matching the seed within tolerance.

    Internally re-uses the same candidate-mask + 4-connected dilation
    that the fill bucket uses (so the wand and the bucket agree on what
    "the same colour as this pixel" means).
    """
    from Imervue.paint.fill import _contiguous_region

    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"magic_wand_mask expects HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    h, w = canvas.shape[:2]
    sx, sy = int(round(seed_x)), int(round(seed_y))
    if not (0 <= sx < w and 0 <= sy < h):
        return np.zeros((h, w), dtype=np.bool_)

    seed = canvas[sy, sx, :3].astype(np.int16)
    diff = np.abs(canvas[..., :3].astype(np.int16) - seed[None, None, :])
    candidates = diff.max(axis=-1) <= max(0, min(255, int(tolerance)))
    if contiguous:
        return _contiguous_region(candidates, sx, sy)
    return candidates
