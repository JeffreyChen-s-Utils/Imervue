"""Stroke a selection's boundary — Edit-menu verb.

Pure-numpy: takes a HxW bool selection + an HxWx4 layer canvas
and writes a coloured rim of configurable thickness around the
selection's edge into the canvas.

Three placements mirror Photoshop / MediBang:

* ``"outside"`` — the rim sits entirely outside the selection
  (selection grows by ``width`` pixels).
* ``"inside"``  — the rim sits entirely inside the selection
  (selection shrinks by ``width`` pixels).
* ``"center"``  — the rim straddles the boundary; ``width//2``
  pixels each side.

The boundary is computed via 4-connected dilation / erosion — same
trick used by :mod:`Imervue.paint.layer_effects` for stroke FX, kept
here as a separate copy so a refactor of one doesn't surprise the
other.
"""
from __future__ import annotations

import numpy as np

STROKE_PLACEMENTS = ("outside", "inside", "center")
DEFAULT_PLACEMENT = "outside"
MIN_STROKE_WIDTH = 1
MAX_STROKE_WIDTH = 64


def stroke_selection(
    canvas: np.ndarray,
    selection: np.ndarray,
    color: tuple[int, int, int, int],
    *, width: int = 2,
    placement: str = DEFAULT_PLACEMENT,
) -> bool:
    """Paint a coloured rim along ``selection``'s boundary into ``canvas``.

    Returns ``True`` if any pixel was written. Empty selections,
    zero-width strokes, or a placement that produces no rim (e.g.
    inside-stroke on a 1-pixel selection) all return ``False`` after
    a no-op — matches the layer-effects stroke convention.
    """
    if (
        canvas.ndim != 3
        or canvas.shape[2] != 4
        or canvas.dtype != np.uint8
    ):
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape}"
            f" {canvas.dtype}",
        )
    if selection.ndim != 2 or selection.dtype != np.bool_:
        raise ValueError(
            f"selection must be HxW bool, got {selection.shape}"
            f" {selection.dtype}",
        )
    if selection.shape != canvas.shape[:2]:
        raise ValueError(
            f"selection shape {selection.shape} does not match canvas"
            f" {canvas.shape[:2]}",
        )
    if placement not in STROKE_PLACEMENTS:
        raise ValueError(
            f"placement must be one of {STROKE_PLACEMENTS}, got {placement!r}",
        )
    width = int(width)
    if not MIN_STROKE_WIDTH <= width <= MAX_STROKE_WIDTH:
        raise ValueError(
            f"width must be in [{MIN_STROKE_WIDTH}, {MAX_STROKE_WIDTH}],"
            f" got {width}",
        )
    if not selection.any():
        return False
    rim = _rim_mask(selection, width=width, placement=placement)
    if not rim.any():
        return False
    canvas[rim] = color
    return True


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _rim_mask(
    selection: np.ndarray, *, width: int, placement: str,
) -> np.ndarray:
    """Compute the rim mask the caller paints into the canvas."""
    if placement == "outside":
        outer = _dilate(selection, width)
        return outer & ~selection
    if placement == "inside":
        inner = _erode(selection, width)
        return selection & ~inner
    # center: half outside, half inside (rounded so an odd width
    # gets the extra pixel on the outside, matching Photoshop).
    inside_w = width // 2
    outside_w = width - inside_w
    grown = _dilate(selection, outside_w) if outside_w > 0 else selection
    shrunk = _erode(selection, inside_w) if inside_w > 0 else selection
    return grown & ~shrunk


def _dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    """4-connected dilation by ``iterations`` pixels."""
    if iterations <= 0:
        return mask.copy()
    out = mask.copy()
    for _ in range(iterations):
        up = np.zeros_like(out)
        up[1:] = out[:-1]
        down = np.zeros_like(out)
        down[:-1] = out[1:]
        left = np.zeros_like(out)
        left[:, 1:] = out[:, :-1]
        right = np.zeros_like(out)
        right[:, :-1] = out[:, 1:]
        out = out | up | down | left | right
    return out


def _erode(mask: np.ndarray, iterations: int) -> np.ndarray:
    """4-connected erosion by ``iterations`` pixels."""
    if iterations <= 0:
        return mask.copy()
    out = mask.copy()
    for _ in range(iterations):
        up = np.zeros_like(out)
        up[:-1] = out[1:]
        down = np.zeros_like(out)
        down[1:] = out[:-1]
        left = np.zeros_like(out)
        left[:, :-1] = out[:, 1:]
        right = np.zeros_like(out)
        right[:, 1:] = out[:, :-1]
        out = out & up & down & left & right
    return out
