"""Line-cleanup helpers — Chaikin smoothing + small-gap closing.

Two utilities a comic / illustration artist reaches for after a
quick sketch:

* :func:`smooth_polyline` — Chaikin's corner-cutting algorithm.
  Each iteration replaces every segment with two interpolated
  points at 1/4 and 3/4 along the segment, doubling the polyline
  length while rounding sharp corners. Two passes give a noticeably
  smoother line; four are usually enough for a hand-drawn ink line.
* :func:`close_small_gaps` — for a binary line mask (1 where the
  ink is), fill in tiny holes shorter than ``max_gap`` pixels via a
  morphological close. Useful for prepping a flood-fill on a mostly-
  closed sketch where the line work has tiny breaks.

Pure-numpy. Public API is friendly to the existing
``image_trace.simplify_polyline`` consumers — both take ``list of
(x, y)`` tuples — so callers can chain "trace → simplify → smooth"
without a translation layer.
"""
from __future__ import annotations

import numpy as np

CHAIKIN_DEFAULT_ITERATIONS = 2
CHAIKIN_MAX_ITERATIONS = 8

GAP_CLOSE_MIN = 1
GAP_CLOSE_MAX = 32


# ---------------------------------------------------------------------------
# Chaikin smoothing
# ---------------------------------------------------------------------------


def smooth_polyline(
    polyline: list[tuple[float, float]],
    *,
    iterations: int = CHAIKIN_DEFAULT_ITERATIONS,
    closed: bool = False,
) -> list[tuple[float, float]]:
    """Smooth ``polyline`` via Chaikin's corner-cutting algorithm.

    ``iterations`` controls how aggressively corners are rounded;
    each iteration roughly doubles the point count so 6+ on a long
    polyline gets expensive. ``closed=True`` wraps the polyline so
    the start point is treated as adjacent to the end — useful when
    the input is a closed contour from :mod:`image_trace`.

    Inputs of length < 3 pass through unchanged because Chaikin
    needs at least one segment between two corners to cut. Empty
    inputs return an empty list.
    """
    if iterations < 0:
        raise ValueError(f"iterations must be >= 0, got {iterations}")
    if iterations > CHAIKIN_MAX_ITERATIONS:
        raise ValueError(
            f"iterations must be <= {CHAIKIN_MAX_ITERATIONS}, got {iterations}",
        )
    if iterations == 0 or len(polyline) < 3:
        return [(float(x), float(y)) for x, y in polyline]
    points = [(float(x), float(y)) for x, y in polyline]
    for _ in range(iterations):
        points = _chaikin_pass(points, closed=closed)
    return points


def _chaikin_pass(
    points: list[tuple[float, float]], *, closed: bool,
) -> list[tuple[float, float]]:
    """One Chaikin step — replace segments with their 1/4 + 3/4 cuts."""
    n = len(points)
    if n < 2:
        return list(points)
    out: list[tuple[float, float]] = []
    if not closed:
        out.append(points[0])
    pairs = list(zip(points, points[1:] + ([points[0]] if closed else []), strict=False))
    for (x0, y0), (x1, y1) in pairs:
        out.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
        out.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
    if not closed:
        out.append(points[-1])
    return out


# ---------------------------------------------------------------------------
# Gap closing
# ---------------------------------------------------------------------------


def close_small_gaps(
    line_mask: np.ndarray,
    *,
    max_gap: int = 2,
) -> np.ndarray:
    """Fill tiny holes in a binary line mask via morphological close.

    ``line_mask`` is HxW bool — ``True`` for ink pixels, ``False``
    for background. A morphological closing with a square kernel of
    side ``2 * max_gap + 1`` fills holes shorter than ``max_gap`` in
    every direction. Larger gaps stay open — the algorithm doesn't
    extrapolate; it only joins lines that are already close enough.

    Returns a fresh mask; the input is never mutated.
    """
    if line_mask.ndim != 2:
        raise ValueError(
            f"line_mask must be 2-D, got {line_mask.shape}",
        )
    if line_mask.dtype != np.bool_:
        raise ValueError(
            f"line_mask dtype must be bool, got {line_mask.dtype}",
        )
    if not GAP_CLOSE_MIN <= int(max_gap) <= GAP_CLOSE_MAX:
        raise ValueError(
            f"max_gap must be in [{GAP_CLOSE_MIN}, {GAP_CLOSE_MAX}], "
            f"got {max_gap!r}",
        )
    radius = int(max_gap)
    dilated = _dilate(line_mask, radius)
    closed = _erode(dilated, radius)
    return closed


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Square-kernel dilation — a True pixel grows by ``radius`` each side."""
    if radius <= 0:
        return mask.copy()
    h, w = mask.shape
    out = np.zeros_like(mask)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ys = slice(max(0, dy), min(h, h + dy))
            xs = slice(max(0, dx), min(w, w + dx))
            sys = slice(max(0, -dy), min(h, h - dy))
            sxs = slice(max(0, -dx), min(w, w - dx))
            out[ys, xs] |= mask[sys, sxs]
    return out


def _erode(mask: np.ndarray, radius: int) -> np.ndarray:
    """Square-kernel erosion — inverse of :func:`_dilate`."""
    if radius <= 0:
        return mask.copy()
    h, w = mask.shape
    out = np.ones_like(mask)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ys = slice(max(0, dy), min(h, h + dy))
            xs = slice(max(0, dx), min(w, w + dx))
            sys = slice(max(0, -dy), min(h, h - dy))
            sxs = slice(max(0, -dx), min(w, w - dx))
            out[ys, xs] &= mask[sys, sxs]
    # Clamp away from off-canvas region so the erosion doesn't bleed
    # the edge in (the dilation already extended out, but erosion's
    # initial all-ones means edge pixels would survive).
    out[:radius, :] = False
    out[-radius:, :] = False
    out[:, :radius] = False
    out[:, -radius:] = False
    # Recombine — anywhere the dilated mask was True we keep the
    # eroded result; outside that, False.
    return out
