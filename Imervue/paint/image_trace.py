"""Image-trace / vectorise — convert a binary mask to polyline contours.

Implements a marching-squares pass over a bool / non-zero alpha mask
to produce a set of line segments, then walks the segment graph to
assemble continuous polylines. Useful for "vectorise this sketch"
workflows or for laying down a pen-tool path along a layer's
silhouette.

The output is a list of polylines, each itself a list of
``(x, y)`` floats in image coordinates. Segments live on cell
midpoints (so coordinates are typically 0.5-stepped) — the caller
can quantise back to ints if a pixel-grid path is needed.

Pure numpy / Python; the marching-squares table is a 16-entry
dictionary so the per-cell decision is constant time.
"""
from __future__ import annotations

import numpy as np

# Marching-squares segment table.
# Bit packing: bit 0 = TL, bit 1 = TR, bit 2 = BR, bit 3 = BL.
# Segment endpoints in cell-local coordinates (0..1 along each axis):
# top edge midpoint = (0.5, 0), right = (1, 0.5), bottom = (0.5, 1),
# left = (0, 0.5).
_TOP = (0.5, 0.0)
_RIGHT = (1.0, 0.5)
_BOTTOM = (0.5, 1.0)
_LEFT = (0.0, 0.5)

# Each pattern entry is a list of (start, end) segment pairs.
_PATTERNS: dict[int, list[tuple[tuple[float, float], tuple[float, float]]]] = {
    0:  [],
    1:  [(_LEFT, _TOP)],            # TL only
    2:  [(_TOP, _RIGHT)],           # TR only
    3:  [(_LEFT, _RIGHT)],          # TL + TR (top row)
    4:  [(_RIGHT, _BOTTOM)],        # BR only
    5:  [(_LEFT, _TOP), (_RIGHT, _BOTTOM)],   # saddle
    6:  [(_TOP, _BOTTOM)],          # TR + BR (right column)
    7:  [(_LEFT, _BOTTOM)],         # TL + TR + BR
    8:  [(_LEFT, _BOTTOM)],         # BL only
    9:  [(_TOP, _BOTTOM)],          # TL + BL (left column)
    10: [(_LEFT, _BOTTOM), (_TOP, _RIGHT)],   # saddle
    11: [(_TOP, _BOTTOM)],          # TL + TR + BL — wait, recompute
    12: [(_LEFT, _RIGHT)],          # BR + BL (bottom row)
    13: [(_TOP, _RIGHT)],           # TL + BR + BL
    14: [(_LEFT, _TOP)],            # TR + BR + BL
    15: [],
}

# Re-derive entries 7, 11, 13, 14: each is the 3-corner-set whose
# bit pattern leaves one corner *off*. The single open corner's two
# adjacent edge midpoints form the segment.
_PATTERNS[7] = [(_LEFT, _BOTTOM)]    # TL+TR+BR set; BL off → left↔bottom
_PATTERNS[11] = [(_RIGHT, _BOTTOM)]  # TL+TR+BL set; BR off → right↔bottom
_PATTERNS[13] = [(_LEFT, _TOP)]      # TL+BR+BL set; TR off → left↔top
_PATTERNS[14] = [(_TOP, _RIGHT)]     # TR+BR+BL set; TL off → top↔right


def find_segments(
    mask: np.ndarray,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Run marching squares and return the raw line segments.

    ``mask`` is HxW bool (or any 2-D array — non-zero is treated as
    "inside"). Segments are emitted in cell scan order. The output
    is a flat list, not yet linked into polylines.
    """
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {mask.shape}")
    binary = mask.astype(bool)
    h, w = binary.shape
    if h < 2 or w < 2:
        return []

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for y in range(h - 1):
        for x in range(w - 1):
            tl = int(binary[y, x])
            tr = int(binary[y, x + 1])
            br = int(binary[y + 1, x + 1])
            bl = int(binary[y + 1, x])
            pattern = tl | (tr << 1) | (br << 2) | (bl << 3)
            cell_segments = _PATTERNS.get(pattern, [])
            for (sx, sy), (ex, ey) in cell_segments:
                segments.append((
                    (x + sx, y + sy),
                    (x + ex, y + ey),
                ))
    return segments


def find_contours(
    mask: np.ndarray,
) -> list[list[tuple[float, float]]]:
    """Return a list of polyline contours covering the boundaries
    of the True region(s) in ``mask``.

    Each polyline is a list of ``(x, y)`` floats. Closed contours
    end at their starting point so the caller can render them as
    a closed path. Open contours (rare with a marching-squares
    source on a finite mask) end at their final segment endpoint.
    """
    segments = find_segments(mask)
    if not segments:
        return []
    return _link_segments(segments)


def _link_segments(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Walk a segment list, linking head-to-tail into polylines."""
    # Build adjacency: each endpoint maps to a list of segment indices.
    adjacency: dict[tuple[float, float], list[int]] = {}
    for i, (a, b) in enumerate(segments):
        adjacency.setdefault(a, []).append(i)
        adjacency.setdefault(b, []).append(i)

    consumed = [False] * len(segments)
    polylines: list[list[tuple[float, float]]] = []
    for seed_idx, (a, b) in enumerate(segments):
        if consumed[seed_idx]:
            continue
        consumed[seed_idx] = True
        polyline = [a, b]
        _walk_chain(polyline, b, segments, adjacency, consumed, append=True)
        _walk_chain(polyline, a, segments, adjacency, consumed, append=False)
        polylines.append(polyline)
    return polylines


def _walk_chain(
    polyline: list[tuple[float, float]],
    start: tuple[float, float],
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    adjacency: dict[tuple[float, float], list[int]],
    consumed: list[bool],
    *,
    append: bool,
) -> None:
    """Extend ``polyline`` from ``start`` along unused adjacent segments.

    ``append=True`` walks forward and tail-extends; ``append=False``
    walks backward and head-extends. Stops when there are no unused
    neighbours, or when the chain closes onto the polyline's other
    end (forming a loop).
    """
    current = start
    while True:
        options = [i for i in adjacency.get(current, []) if not consumed[i]]
        if not options:
            return
        next_idx = options[0]
        consumed[next_idx] = True
        seg = segments[next_idx]
        other = seg[1] if seg[0] == current else seg[0]
        if append:
            polyline.append(other)
            if other == polyline[0]:
                return
        else:
            polyline.insert(0, other)
            if other == polyline[-1]:
                return
        current = other


def simplify_polyline(
    polyline: list[tuple[float, float]],
    *,
    tolerance: float = 1.0,
) -> list[tuple[float, float]]:
    """Douglas–Peucker simplification — remove points that lie within
    ``tolerance`` of the line through their neighbours.

    Pure-Python; recursion depth is logarithmic in the polyline
    length so a 100k-point trace doesn't blow the stack."""
    if tolerance <= 0 or len(polyline) <= 2:
        return list(polyline)

    def _segment_distance(point, line_start, line_end):
        x, y = point
        x0, y0 = line_start
        x1, y1 = line_end
        dx = x1 - x0
        dy = y1 - y0
        if dx == 0 and dy == 0:
            return ((x - x0) ** 2 + (y - y0) ** 2) ** 0.5
        t = ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = x0 + t * dx
        proj_y = y0 + t * dy
        return ((x - proj_x) ** 2 + (y - proj_y) ** 2) ** 0.5

    def _simplify(start: int, end: int, keep: list[bool]) -> None:
        if end <= start + 1:
            return
        max_dist = 0.0
        max_i = start
        for i in range(start + 1, end):
            dist = _segment_distance(
                polyline[i], polyline[start], polyline[end],
            )
            if dist > max_dist:
                max_dist = dist
                max_i = i
        if max_dist > tolerance:
            keep[max_i] = True
            _simplify(start, max_i, keep)
            _simplify(max_i, end, keep)

    keep = [False] * len(polyline)
    keep[0] = True
    keep[-1] = True
    _simplify(0, len(polyline) - 1, keep)
    return [pt for pt, k in zip(polyline, keep, strict=True) if k]
