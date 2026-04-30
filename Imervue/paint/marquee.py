"""Selection marquee — render the boundary of a bool mask as line segments.

Pure-numpy edge extraction so the result can be unit tested without a
display server. The Qt/GL canvas takes the segment array and draws it
twice (offset) for the classic black-on-white marching-ants outline.

The returned array is shape ``(N, 4)`` of ``int32`` rows
``(x0, y0, x1, y1)`` — one row per unit-length boundary segment in
image-space pixel coordinates. Endpoints describe the corner of the
pixel pair, so a segment along the right edge of pixel ``(x, y)`` runs
from ``(x+1, y)`` to ``(x+1, y+1)``.

Performance note: the extraction is two boolean diffs and a pair of
``np.column_stack`` calls — O(N) over the canvas. A 4 MP selection
yields tens of thousands of segments; batching them as a single
``np.array`` keeps the GL draw call count to one.
"""
from __future__ import annotations

import numpy as np


def selection_outline_segments(mask: np.ndarray) -> np.ndarray:
    """Return ``(N, 4) int32`` array of unit boundary segments."""
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {mask.shape}")
    if mask.dtype != np.bool_:
        raise ValueError(f"mask must be bool, got dtype {mask.dtype}")
    if mask.size == 0 or not mask.any():
        return np.empty((0, 4), dtype=np.int32)

    h, w = mask.shape
    segments: list[np.ndarray] = []

    # Vertical edges between pixel columns x and x+1 (interior boundary).
    vertical = mask[:, :-1] ^ mask[:, 1:]   # H × (W-1)
    if vertical.any():
        ys, xs = np.where(vertical)
        # Edge sits on x = xs+1.
        seg = np.column_stack([
            xs + 1, ys, xs + 1, ys + 1,
        ]).astype(np.int32)
        segments.append(seg)

    # Horizontal edges between pixel rows y and y+1.
    horizontal = mask[:-1, :] ^ mask[1:, :]   # (H-1) × W
    if horizontal.any():
        ys, xs = np.where(horizontal)
        # Edge sits on y = ys+1.
        seg = np.column_stack([
            xs, ys + 1, xs + 1, ys + 1,
        ]).astype(np.int32)
        segments.append(seg)

    # Outer canvas-edge boundary — selection touching x=0 / x=W-1 / y=0 / y=H-1.
    if mask[:, 0].any():
        ys = np.where(mask[:, 0])[0]
        seg = np.column_stack([
            np.zeros_like(ys), ys, np.zeros_like(ys), ys + 1,
        ]).astype(np.int32)
        segments.append(seg)
    if mask[:, -1].any():
        ys = np.where(mask[:, -1])[0]
        seg = np.column_stack([
            np.full_like(ys, w), ys, np.full_like(ys, w), ys + 1,
        ]).astype(np.int32)
        segments.append(seg)
    if mask[0, :].any():
        xs = np.where(mask[0, :])[0]
        seg = np.column_stack([
            xs, np.zeros_like(xs), xs + 1, np.zeros_like(xs),
        ]).astype(np.int32)
        segments.append(seg)
    if mask[-1, :].any():
        xs = np.where(mask[-1, :])[0]
        seg = np.column_stack([
            xs, np.full_like(xs, h), xs + 1, np.full_like(xs, h),
        ]).astype(np.int32)
        segments.append(seg)

    if not segments:
        return np.empty((0, 4), dtype=np.int32)
    return np.vstack(segments)


def bounding_rect(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Return ``(x0, y0, x1, y1)`` covering all True pixels, or ``None``."""
    if mask.ndim != 2 or mask.dtype != np.bool_:
        raise ValueError(f"mask must be 2-D bool, got {mask.shape} {mask.dtype}")
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
