"""Snap-to-edge helpers for shape / crop / transform drags.

Computes the candidate snap lines (canvas edges, canvas centre, and
each layer's non-transparent bounding-box edges) and provides a
:func:`snap_point` helper that pulls a free-floating drag point onto
the nearest candidate within a configurable threshold.

Pure-numpy / Qt-free. The visual rendering of snap guides (green
lines under the cursor) is the canvas widget's job — a future
revision can read the same candidate lists to draw them.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

DEFAULT_SNAP_THRESHOLD_PX = 6
SNAP_VERTICAL = "x"   # candidate is a vertical line at constant x
SNAP_HORIZONTAL = "y"   # candidate is a horizontal line at constant y


def collect_canvas_candidates(
    canvas_shape: tuple[int, int],
) -> tuple[list[float], list[float]]:
    """Return ``(x_candidates, y_candidates)`` for the canvas itself.

    Includes the four edges and the centre line on each axis — the
    five most useful alignment targets a user expects when no other
    layer geometry is around.
    """
    h, w = canvas_shape
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas_shape must be positive, got {canvas_shape}")
    return (
        [0.0, w / 2.0, float(w)],
        [0.0, h / 2.0, float(h)],
    )


def collect_layer_candidates(
    layer_images: Iterable[np.ndarray],
) -> tuple[list[float], list[float]]:
    """Return ``(x_candidates, y_candidates)`` from each layer's
    non-transparent bounding box.

    Each layer contributes up to four edges (left/right/top/bottom).
    Empty / fully-transparent layers contribute nothing.
    """
    xs: list[float] = []
    ys: list[float] = []
    for image in layer_images:
        if (
            image.ndim != 3
            or image.shape[2] != 4
            or image.dtype != np.uint8
        ):
            continue
        alpha = image[..., 3]
        if not alpha.any():
            continue
        rows = np.where(alpha.any(axis=1))[0]
        cols = np.where(alpha.any(axis=0))[0]
        if rows.size == 0 or cols.size == 0:
            continue
        ys.append(float(rows[0]))
        ys.append(float(rows[-1] + 1))
        xs.append(float(cols[0]))
        xs.append(float(cols[-1] + 1))
    return (xs, ys)


def snap_point(
    x: float, y: float,
    *,
    x_candidates: Iterable[float] = (),
    y_candidates: Iterable[float] = (),
    threshold: float = DEFAULT_SNAP_THRESHOLD_PX,
) -> tuple[float, float, list[tuple[str, float]]]:
    """Pull ``(x, y)`` onto the nearest candidate within ``threshold``.

    Returns ``(snapped_x, snapped_y, hits)`` where ``hits`` is the
    list of ``(axis, value)`` candidates the point ended up snapped
    to (one entry per axis at most). The third value lets the canvas
    overlay highlight just the lines that are currently active.

    ``threshold <= 0`` disables snapping (everything passes through
    unchanged with an empty hit list).
    """
    if threshold <= 0:
        return (float(x), float(y), [])
    snapped_x, x_hit = _snap_axis(float(x), x_candidates, threshold)
    snapped_y, y_hit = _snap_axis(float(y), y_candidates, threshold)
    hits: list[tuple[str, float]] = []
    if x_hit is not None:
        hits.append((SNAP_VERTICAL, x_hit))
    if y_hit is not None:
        hits.append((SNAP_HORIZONTAL, y_hit))
    return (snapped_x, snapped_y, hits)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _snap_axis(
    value: float,
    candidates: Iterable[float],
    threshold: float,
) -> tuple[float, float | None]:
    """Snap ``value`` to the closest entry in ``candidates`` within
    ``threshold``. Returns ``(snapped, hit_value_or_None)``."""
    best_distance = float("inf")
    best_value: float | None = None
    for candidate in candidates:
        cv = float(candidate)
        d = abs(value - cv)
        if d < best_distance:
            best_distance = d
            best_value = cv
    if best_value is None or best_distance > threshold:
        return (value, None)
    return (best_value, best_value)
