"""Pure-numpy gradient rasterisation.

Four full-featured gradient kinds, parameterised by two image-space
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


_T_FIELD_BUILDERS = {
    "linear": lambda xx, yy, x0, y0, x1, y1: _linear_t(xx, yy, x0, y0, x1, y1),
    "radial": lambda xx, yy, x0, y0, x1, y1: _radial_t(xx, yy, x0, y0, x1, y1),
    "angle": lambda xx, yy, x0, y0, x1, y1: _angle_t(xx, yy, x0, y0, x1, y1),
    "diamond": lambda xx, yy, x0, y0, x1, y1: _diamond_t(xx, yy, x0, y0, x1, y1),
}


def _validate_gradient_inputs(
    canvas: np.ndarray,
    kind: str,
    selection: np.ndarray | None,
) -> None:
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


def _pick_endpoint_color(
    primary: tuple[int, int, int] | None,
    other: tuple[int, int, int] | None,
) -> tuple[int, int, int]:
    """Return ``primary`` when present, falling back to ``other`` and
    finally to opaque black so the rgb mix never sees ``None``."""
    if primary is not None:
        return primary
    if other is not None:
        return other
    return (0, 0, 0)


def _resolve_endpoint_colors(
    fg: tuple[int, int, int] | None,
    bg: tuple[int, int, int] | None,
) -> tuple[tuple[int, int, int], tuple[int, int, int], float, float]:
    """Resolve ``None`` endpoints into a colour pair plus alpha
    factors. The substitution keeps the rgb mix meaningful while the
    alpha factors carry the fade-to-transparent."""
    fg_color = _pick_endpoint_color(fg, bg)
    bg_color = _pick_endpoint_color(bg, fg)
    fg_alpha = 0.0 if fg is None else 1.0
    bg_alpha = 0.0 if bg is None else 1.0
    return fg_color, bg_color, fg_alpha, bg_alpha


def render_gradient(
    canvas: np.ndarray,
    p0: tuple[float, float],
    p1: tuple[float, float],
    fg: tuple[int, int, int] | None,
    bg: tuple[int, int, int] | None,
    *,
    kind: str = DEFAULT_GRADIENT_KIND,
    reverse: bool = False,
    selection: np.ndarray | None = None,
) -> bool:
    """Fill ``canvas`` with a gradient between ``p0`` (fg) and ``p1`` (bg).

    ``fg`` or ``bg`` may be ``None`` to mean "transparent at this
    endpoint" — the per-pixel alpha then fades from 1.0 at the
    opaque side to 0.0 at the transparent side. With both endpoints
    set to a colour the alpha stays opaque (legacy behaviour). Both
    endpoints ``None`` produces a fully-transparent fill, which the
    user usually doesn't want; we still write so the selection /
    bounding-box behaviour is consistent with the coloured cases.

    Returns ``True`` if any pixel was written, ``False`` if the drag
    collapsed to a point (start == end) or the kind is unknown.
    """
    _validate_gradient_inputs(canvas, kind, selection)
    h, w = canvas.shape[:2]

    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    if x0 == x1 and y0 == y1:
        return False

    yy, xx = np.indices((h, w), dtype=np.float32)
    t = _T_FIELD_BUILDERS[kind](xx, yy, x0, y0, x1, y1)
    t = np.clip(t, 0.0, 1.0)
    if reverse:
        t = 1.0 - t

    fg_color, bg_color, fg_alpha, bg_alpha = _resolve_endpoint_colors(fg, bg)
    fg_arr = np.array(fg_color, dtype=np.float32)
    bg_arr = np.array(bg_color, dtype=np.float32)
    rgb = fg_arr[None, None, :] * (1.0 - t[..., None]) + bg_arr[None, None, :] * t[..., None]
    rgb = np.clip(rgb, 0.0, 255.0).astype(np.uint8)
    alpha_field = fg_alpha * (1.0 - t) + bg_alpha * t
    alpha_u8 = np.clip(alpha_field * 255.0, 0.0, 255.0).astype(np.uint8)

    mask = selection if selection is not None else np.ones((h, w), dtype=np.bool_)

    canvas[mask, :3] = rgb[mask]
    canvas[mask, 3] = alpha_u8[mask]
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
