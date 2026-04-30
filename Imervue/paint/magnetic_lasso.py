"""Edge-snapping magnetic lasso helper.

Photoshop's Magnetic Lasso anchors itself to the strongest nearby
edge as the cursor moves. This module supplies the snap math: given
an image and a candidate anchor point, search a local window for
the pixel with the highest edge-magnitude value (Sobel-style finite
difference) and return that location.

Pure numpy. No scipy / OpenCV dependency — the gradient comes from
``numpy.gradient`` plus a Pythagorean magnitude.
"""
from __future__ import annotations

import numpy as np

DEFAULT_SEARCH_RADIUS = 10
MAX_SEARCH_RADIUS = 256


def edge_magnitude(image: np.ndarray) -> np.ndarray:
    """Return an HxW float32 edge-magnitude map for ``image``.

    Computes per-pixel Rec.601 luminance, then a Sobel-flavoured
    gradient (``numpy.gradient`` along each axis) and combines via
    Pythagorean magnitude. The result is uncalibrated — relative
    values are what matter for finding peaks."""
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    rgb = image[..., :3].astype(np.float32)
    luminance = (
        0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    )
    gy, gx = np.gradient(luminance)
    return np.sqrt(gx * gx + gy * gy).astype(np.float32)


def snap_to_edge(
    image: np.ndarray,
    anchor: tuple[int, int],
    *,
    search_radius: int = DEFAULT_SEARCH_RADIUS,
    edge_map: np.ndarray | None = None,
) -> tuple[int, int]:
    """Find the strongest-edge pixel within ``search_radius`` of
    ``anchor`` and return its coordinates.

    ``edge_map`` (optional) lets the caller pre-compute the edge
    magnitude once and pass it for every anchor — useful when
    snapping a long polyline so we don't recompute the gradient
    HxW times. If omitted, the edge map is computed in place.

    Out-of-bounds anchors clamp to the image; an entirely off-canvas
    anchor returns the anchor unchanged.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    if not 0 <= int(search_radius) <= MAX_SEARCH_RADIUS:
        raise ValueError(
            f"search_radius must be in [0, {MAX_SEARCH_RADIUS}], "
            f"got {search_radius!r}",
        )
    h, w = image.shape[:2]
    ax = int(anchor[0])
    ay = int(anchor[1])
    if not (0 <= ax < w and 0 <= ay < h):
        return (ax, ay)

    if edge_map is None:
        edge_map = edge_magnitude(image)
    elif edge_map.shape != (h, w):
        raise ValueError(
            f"edge_map shape {edge_map.shape} does not match "
            f"image {(h, w)}",
        )

    if search_radius == 0:
        return (ax, ay)

    x0 = max(0, ax - search_radius)
    y0 = max(0, ay - search_radius)
    x1 = min(w, ax + search_radius + 1)
    y1 = min(h, ay + search_radius + 1)
    region = edge_map[y0:y1, x0:x1]
    if not region.size:
        return (ax, ay)
    if region.max() <= 0:
        # Uniform region — no edge to snap to. Return the anchor.
        return (ax, ay)
    flat_index = int(np.argmax(region))
    rel_y, rel_x = np.unravel_index(flat_index, region.shape)
    return (x0 + int(rel_x), y0 + int(rel_y))


def snap_path_to_edges(
    image: np.ndarray,
    anchors: list[tuple[int, int]],
    *,
    search_radius: int = DEFAULT_SEARCH_RADIUS,
) -> list[tuple[int, int]]:
    """Snap each anchor in a polyline to its nearest strong edge.

    The edge map is computed once and shared across every anchor —
    O(HxW) work for the gradient plus O(R²) per anchor.
    """
    if not anchors:
        return []
    edge_map = edge_magnitude(image)
    return [
        snap_to_edge(
            image, anchor,
            search_radius=search_radius, edge_map=edge_map,
        )
        for anchor in anchors
    ]
