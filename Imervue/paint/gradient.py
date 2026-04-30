"""Pure-numpy gradient rasterisation.

Four MediBang-style gradient kinds, parameterised by two image-space
points and the foreground / background colours. The drag start point
holds the foreground; the drag end holds the background. A ``reverse``
flag swaps the role of the two colours without re-issuing the drag.

* linear — projection of pixel onto the start→end line
* radial — distance from start, normalised by start→end length
* angle — winding angle around start, with the 0° tick aligned to
  start→end
* diamond — Manhattan distance, the classic Photoshop diamond
  gradient
"""
from __future__ import annotations

import numpy as np

GRADIENT_KINDS = ("linear", "radial", "angle", "diamond")
DEFAULT_GRADIENT_KIND = "linear"


def render_gradient(
    canvas: np.ndarray,
    p0: tuple[float, float],
    p1: tuple[float, float],
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    *,
    kind: str = DEFAULT_GRADIENT_KIND,
    reverse: bool = False,
    selection: np.ndarray | None = None,
) -> bool:
    """Fill ``canvas`` with a gradient between ``p0`` (fg) and ``p1`` (bg).

    Returns ``True`` if any pixel was written, ``False`` if the drag
    collapsed to a point (start == end) or the kind is unknown.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    if kind not in GRADIENT_KINDS:
        raise ValueError(
            f"unknown gradient kind {kind!r}; expected one of {GRADIENT_KINDS}",
        )
    h, w = canvas.shape[:2]
    if selection is not None and selection.shape != (h, w):
        raise ValueError(
            f"selection shape {selection.shape} does not match canvas {(h, w)}",
        )

    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    if x0 == x1 and y0 == y1:
        return False

    yy, xx = np.indices((h, w), dtype=np.float32)
    if kind == "linear":
        t = _linear_t(xx, yy, x0, y0, x1, y1)
    elif kind == "radial":
        t = _radial_t(xx, yy, x0, y0, x1, y1)
    elif kind == "angle":
        t = _angle_t(xx, yy, x0, y0, x1, y1)
    else:  # diamond
        t = _diamond_t(xx, yy, x0, y0, x1, y1)

    t = np.clip(t, 0.0, 1.0)
    if reverse:
        t = 1.0 - t

    fg_arr = np.array(fg, dtype=np.float32)
    bg_arr = np.array(bg, dtype=np.float32)
    rgb = fg_arr[None, None, :] * (1.0 - t[..., None]) + bg_arr[None, None, :] * t[..., None]
    rgb = np.clip(rgb, 0.0, 255.0).astype(np.uint8)

    mask = selection if selection is not None else np.ones((h, w), dtype=np.bool_)

    canvas[mask, :3] = rgb[mask]
    canvas[mask, 3] = 255
    return True


# ---------------------------------------------------------------------------
# Internal t-field constructors
# ---------------------------------------------------------------------------


def _linear_t(xx, yy, x0, y0, x1, y1) -> np.ndarray:
    dx = x1 - x0
    dy = y1 - y0
    denom = dx * dx + dy * dy
    return ((xx - x0) * dx + (yy - y0) * dy) / denom


def _radial_t(xx, yy, x0, y0, x1, y1) -> np.ndarray:
    dx = x1 - x0
    dy = y1 - y0
    radius = float(np.hypot(dx, dy))
    if radius <= 0:
        return np.zeros_like(xx)
    return np.hypot(xx - x0, yy - y0) / radius


def _angle_t(xx, yy, x0, y0, x1, y1) -> np.ndarray:
    base_angle = np.arctan2(y1 - y0, x1 - x0)
    angles = np.arctan2(yy - y0, xx - x0)
    delta = np.mod(angles - base_angle, 2.0 * np.pi)
    return delta / (2.0 * np.pi)


def _diamond_t(xx, yy, x0, y0, x1, y1) -> np.ndarray:
    radius = float(abs(x1 - x0) + abs(y1 - y0))
    if radius <= 0:
        return np.zeros_like(xx)
    return (np.abs(xx - x0) + np.abs(yy - y0)) / radius
