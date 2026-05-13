"""Pure-Python hit testing for :class:`HitArea` regions.

A hit area's region is the axis-aligned bounding box of every drawable
listed in :attr:`HitArea.drawables` at its *current* vertex positions.
Callers pass in the canvas's deformed-vertex cache so a click on a hair
strand swung sideways still resolves correctly.

Kept Qt-free so the runtime composer + tests can call ``hit_test``
without spinning a widget; the canvas hooks it into ``mousePressEvent``.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from Imervue.puppet.document import Drawable, HitArea, PuppetDocument


def hit_test(
    document: PuppetDocument,
    x: float,
    y: float,
    *,
    deformed_vertices: dict[str, np.ndarray] | None = None,
) -> str | None:
    """Return the id of the topmost hit area at image-space ``(x, y)``,
    or ``None`` when no hit area's box contains the point.

    "Topmost" means the hit area whose member drawables include the
    highest ``draw_order`` — matches the renderer's painter's-algorithm
    so the user always clicks the visually-frontmost region first.
    """
    candidates: list[tuple[int, str]] = []
    for area in document.hit_areas:
        bbox = _area_bbox(document, area, deformed_vertices)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        if x0 <= float(x) <= x1 and y0 <= float(y) <= y1:
            candidates.append((_topmost_draw_order(document, area), area.id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def hit_area_bbox(
    document: PuppetDocument,
    area: HitArea,
    *,
    deformed_vertices: dict[str, np.ndarray] | None = None,
) -> tuple[float, float, float, float] | None:
    """Return the ``(x0, y0, x1, y1)`` AABB for one hit area, or ``None``
    when none of its drawables resolve. Public so debug overlays /
    editor selection rectangles can use the same math as the hit test.
    """
    return _area_bbox(document, area, deformed_vertices)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _area_bbox(
    document: PuppetDocument,
    area: HitArea,
    deformed_vertices: dict[str, np.ndarray] | None,
) -> tuple[float, float, float, float] | None:
    pieces = list(_iter_drawable_arrays(document, area.drawables, deformed_vertices))
    if not pieces:
        return None
    stacked = np.concatenate(pieces, axis=0)
    if stacked.size == 0:
        return None
    x0 = float(stacked[:, 0].min())
    y0 = float(stacked[:, 1].min())
    x1 = float(stacked[:, 0].max())
    y1 = float(stacked[:, 1].max())
    return (x0, y0, x1, y1)


def _iter_drawable_arrays(
    document: PuppetDocument,
    drawable_ids: Iterable[str],
    deformed_vertices: dict[str, np.ndarray] | None,
) -> Iterable[np.ndarray]:
    for drawable_id in drawable_ids:
        drawable = document.drawable(drawable_id)
        if drawable is None:
            continue
        arr = _drawable_array(drawable, deformed_vertices)
        if arr.size:
            yield arr


def _drawable_array(
    drawable: Drawable,
    deformed_vertices: dict[str, np.ndarray] | None,
) -> np.ndarray:
    if deformed_vertices is not None:
        cached = deformed_vertices.get(drawable.id)
        if cached is not None:
            return np.asarray(cached, dtype=np.float64).reshape(-1, 2)
    if not drawable.vertices:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(drawable.vertices, dtype=np.float64)


def _topmost_draw_order(document: PuppetDocument, area: HitArea) -> int:
    """Highest ``draw_order`` across the area's drawables — picks the
    visually-frontmost region when boxes overlap."""
    best = -(1 << 30)
    for drawable_id in area.drawables:
        drawable = document.drawable(drawable_id)
        if drawable is None:
            continue
        best = max(best, drawable.draw_order)
    return best
