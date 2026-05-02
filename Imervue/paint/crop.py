"""Pure-numpy crop helpers — rect, selection-bounds, alpha-bounds.

Three operations:

* :func:`crop_to_rect` — slice an HxWx? array to ``(x, y, w, h)``.
* :func:`selection_bounds` — return the bbox of a bool mask's True
  region, or ``None`` if the mask is empty.
* :func:`non_transparent_bounds` — return the bbox of a layer's
  ``alpha > 0`` region, or ``None`` if fully transparent.

The :class:`Imervue.paint.document.PaintDocument` wraps these in
``crop`` / ``crop_to_selection`` / ``crop_to_non_transparent`` so a
workspace command can crop the whole stack (layers, masks, selection)
together.
"""
from __future__ import annotations

import numpy as np


def crop_to_rect(arr: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    """Return ``arr[y:y+h, x:x+w, ...]`` after validating ``rect``.

    The rect is clamped to the input bounds — passing a rect that
    overshoots the array is allowed and just yields a smaller crop.
    A rect with zero width or height (after clamping) raises
    ``ValueError``.
    """
    if arr.ndim < 2:
        raise ValueError(f"input must be at least 2-D, got {arr.shape}")
    h, w = arr.shape[:2]
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        raise ValueError(f"rect must have positive width and height, got {rect!r}")
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(w, int(x) + int(rw))
    y1 = min(h, int(y) + int(rh))
    if x1 <= x0 or y1 <= y0:
        raise ValueError(
            f"rect {rect!r} does not overlap input shape {arr.shape[:2]}",
        )
    return np.ascontiguousarray(arr[y0:y1, x0:x1])


def selection_bounds(
    selection_mask: np.ndarray,
) -> tuple[int, int, int, int] | None:
    """Return ``(x, y, w, h)`` of the True region, or ``None`` if empty."""
    if selection_mask.dtype != np.bool_:
        raise ValueError(f"selection_mask must be bool, got {selection_mask.dtype}")
    if not selection_mask.any():
        return None
    ys, xs = np.nonzero(selection_mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def non_transparent_bounds(
    layer_image: np.ndarray,
) -> tuple[int, int, int, int] | None:
    """Return the bbox of the alpha > 0 region of an RGBA layer."""
    if (
        layer_image.ndim != 3
        or layer_image.shape[2] != 4
        or layer_image.dtype != np.uint8
    ):
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, "
            f"got {layer_image.shape} {layer_image.dtype}",
        )
    alpha = layer_image[..., 3]
    return selection_bounds(alpha > 0)


def union_bounds(
    *bounds: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    """Return the smallest bbox covering every supplied rect.

    ``None`` entries are skipped. Returns ``None`` when every input is
    ``None`` (e.g. cropping to non-transparent on an entirely empty
    stack — there's nothing to crop to).
    """
    rects = [b for b in bounds if b is not None]
    if not rects:
        return None
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)
