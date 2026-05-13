"""Render text along the active selection's outline.

Glue between the path-text engine (:mod:`Imervue.paint.text_on_path`)
and the workspace: extracts the largest contour from a boolean
selection mask, simplifies it slightly, and renders the supplied
text along that polyline. Returns the rendered HxWx4 RGBA buffer
ready for composite onto the active layer.

Used by the Manga ▸ "Text on selection path" verb so the user can
draw a curve / shape with the marquee, type text, and have the
glyphs follow the contour the way raster paint apps's text-on-path tool does.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.image_trace import find_contours
from Imervue.paint.text_on_path import render_text_on_path

# Drop redundant collinear points the marching-squares trace emits so
# the path-renderer's tangent calculation is stable. This many pixels
# of distance must separate consecutive points; tighter than this
# and floating-point tangents wobble around the glyph baseline.
MIN_POINT_SPACING_PX = 1.5


def render_text_along_selection(
    selection_mask: np.ndarray,
    text: str,
    canvas_shape: tuple[int, int],
    *,
    family: str | None = None,
    size: int = 36,
    color: tuple[int, int, int] = (0, 0, 0),
    bold: bool = False,
    italic: bool = False,
    char_spacing: float = 0.0,
) -> np.ndarray:
    """Trace ``selection_mask``, walk the longest contour, lay out text.

    ``canvas_shape`` is ``(h, w)``; ``selection_mask`` must be the
    same shape and a boolean array. When the selection contains no
    interior or the longest contour is degenerate, returns a fully-
    transparent buffer of the canvas size.
    """
    h, w = canvas_shape
    if selection_mask is None or selection_mask.dtype != bool:
        raise ValueError("selection_mask must be a boolean ndarray")
    if selection_mask.shape != (h, w):
        raise ValueError(
            f"selection_mask shape {selection_mask.shape} does not "
            f"match canvas {(h, w)}",
        )
    contours = find_contours(selection_mask)
    if not contours:
        return np.zeros((h, w, 4), dtype=np.uint8)

    # Use the longest contour — typically the outer boundary of the
    # largest selected region. Marching-squares emits the closed
    # outline starting on a row sweep, so the head of the polyline
    # sits at a deterministic location.
    contour = max(contours, key=len)
    points = _decimate(contour, MIN_POINT_SPACING_PX)
    if len(points) < 2:
        return np.zeros((h, w, 4), dtype=np.uint8)

    return render_text_on_path(
        text, points, (h, w),
        family=family or "",
        size=size, color=color, bold=bold, italic=italic,
        char_spacing=char_spacing,
    )


def _decimate(
    points: list[tuple[float, float]], min_spacing: float,
) -> list[tuple[float, float]]:
    """Drop points closer than ``min_spacing`` to the previous keeper.

    Cheap O(n) walk — keeps the path's overall shape while
    eliminating the dense step-staircase the marching-squares trace
    emits along axis-aligned edges.
    """
    if not points:
        return []
    kept: list[tuple[float, float]] = [points[0]]
    spacing_sq = float(min_spacing) ** 2
    for x, y in points[1:]:
        px, py = kept[-1]
        if (x - px) ** 2 + (y - py) ** 2 >= spacing_sq:
            kept.append((x, y))
    return kept
