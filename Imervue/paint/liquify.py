"""Liquify / warp brushes — push / pinch / bloat / twirl / push-left.

Pure-numpy implementations of the four raster paint apps / Photoshop liquify
brushes. Each call mutates a single brush stroke worth of pixels:
the caller passes the brush centre + radius, plus the per-brush
parameters, and the helper returns a fresh layer image with the
warp applied. Pixels outside the brush radius are returned unchanged.

Each brush builds a *displacement field* over the affected region,
inverts it (so we know which source pixel maps to each output
pixel), and bilinearly resamples the input. Working in inverse-map
space avoids the holes / overlaps that a forward-map approach
would produce when displacements concentrate or diverge.

Out-of-bounds source samples return a fully-transparent pixel,
which the caller can either composite back onto the original (the
brush dispatcher does this) or treat as the warped result.

Brushes:

* :func:`push_warp` — drag every pixel inside the radius by
  ``(dx, dy)``, weighted by a quadratic falloff from the centre.
* :func:`pinch_warp` — pull pixels toward the centre.
* :func:`bloat_warp` — push pixels away from the centre.
* :func:`twirl_warp` — rotate pixels around the centre by a
  weighted angle in degrees.
"""
from __future__ import annotations

import numpy as np

WARP_KINDS = ("push", "pinch", "bloat", "twirl", "push_left")
MAX_RADIUS = 1024


def push_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    dx: float,
    dy: float,
    *,
    strength: float = 1.0,
) -> np.ndarray:
    """Drag every pixel inside the brush radius by ``(dx, dy)``.

    ``strength`` scales the displacement; the per-pixel weight uses a
    quadratic falloff so the centre moves by the full ``(dx, dy)``
    and the edge of the brush footprint barely moves at all.
    """
    _check_image(image)
    radius = _check_radius(radius)
    h, w = image.shape[:2]
    weight = _weight_field(h, w, cx, cy, radius)
    if not weight.any():
        return image.copy()
    xs, ys = _grid(h, w)
    src_x = xs - float(dx) * weight * float(strength)
    src_y = ys - float(dy) * weight * float(strength)
    return _bilinear_sample_rgba(image, src_x, src_y)


def pinch_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    *,
    strength: float = 0.5,
) -> np.ndarray:
    """Pull pixels toward the brush centre."""
    return _radial_warp(image, cx, cy, radius, strength=strength, sign=1.0)


def bloat_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    *,
    strength: float = 0.5,
) -> np.ndarray:
    """Push pixels away from the brush centre."""
    return _radial_warp(image, cx, cy, radius, strength=strength, sign=-1.0)


def twirl_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    *,
    angle_deg: float = 30.0,
    strength: float = 1.0,
) -> np.ndarray:
    """Rotate pixels around the brush centre by ``angle_deg`` (weighted)."""
    _check_image(image)
    radius = _check_radius(radius)
    h, w = image.shape[:2]
    weight = _weight_field(h, w, cx, cy, radius)
    if not weight.any():
        return image.copy()
    xs, ys = _grid(h, w)
    rel_x = xs - cx
    rel_y = ys - cy
    angle = -np.radians(float(angle_deg)) * weight * float(strength)
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    src_x = cos_a * rel_x - sin_a * rel_y + cx
    src_y = sin_a * rel_x + cos_a * rel_y + cy
    return _bilinear_sample_rgba(image, src_x, src_y)


def push_left_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    dx: float,
    dy: float,
    *,
    strength: float = 1.0,
) -> np.ndarray:
    """Displace pixels perpendicular (90° left) to the drag direction.

    Photoshop's "Push Left": dragging smears content to the side of the
    stroke rather than along it, so an edge can be nudged sideways without
    dragging the whole region. Equivalent to :func:`push_warp` with the drag
    vector rotated 90° (``(dx, dy)`` → ``(-dy, dx)``).
    """
    return push_warp(image, cx, cy, radius, -float(dy), float(dx), strength=strength)


def apply_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    *,
    kind: str,
    strength: float = 0.5,
    dx: float = 0.0,
    dy: float = 0.0,
    angle_deg: float = 30.0,
) -> np.ndarray:
    """Dispatch by ``kind`` — convenient single entry point for the
    dispatcher / menu layer."""
    if kind == "push":
        return push_warp(image, cx, cy, radius, dx, dy, strength=strength)
    if kind == "pinch":
        return pinch_warp(image, cx, cy, radius, strength=strength)
    if kind == "bloat":
        return bloat_warp(image, cx, cy, radius, strength=strength)
    if kind == "twirl":
        return twirl_warp(
            image, cx, cy, radius, angle_deg=angle_deg, strength=strength,
        )
    if kind == "push_left":
        return push_left_warp(image, cx, cy, radius, dx, dy, strength=strength)
    raise ValueError(
        f"unknown warp kind {kind!r}; expected one of {WARP_KINDS}",
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _radial_warp(
    image: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    *,
    strength: float,
    sign: float,
) -> np.ndarray:
    _check_image(image)
    radius = _check_radius(radius)
    h, w = image.shape[:2]
    weight = _weight_field(h, w, cx, cy, radius)
    if not weight.any():
        return image.copy()
    xs, ys = _grid(h, w)
    rel_x = xs - cx
    rel_y = ys - cy
    factor = sign * float(strength) * weight
    src_x = xs + rel_x * factor
    src_y = ys + rel_y * factor
    return _bilinear_sample_rgba(image, src_x, src_y)


def _grid(h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.indices((h, w), dtype=np.float32)
    return xs, ys


def _weight_field(
    h: int, w: int, cx: float, cy: float, radius: float,
) -> np.ndarray:
    """Quadratic radial falloff from the brush centre — 1 at the
    centre, 0 at and beyond the radius."""
    ys, xs = np.indices((h, w), dtype=np.float32)
    rel_x = xs - float(cx)
    rel_y = ys - float(cy)
    dist = np.sqrt(rel_x * rel_x + rel_y * rel_y)
    if radius <= 0:
        return np.zeros_like(dist)
    raw = 1.0 - dist / float(radius)
    return np.clip(raw, 0.0, 1.0) ** 2


def _bilinear_sample_rgba(
    image: np.ndarray, xs: np.ndarray, ys: np.ndarray,
) -> np.ndarray:
    """Bilinear sample HxWx4 RGBA at fractional coordinates.

    Out-of-bounds samples return ``(0, 0, 0, 0)`` so the warped result
    has fully-transparent pixels where the source mapped off-canvas;
    callers can composite them back onto the original or treat the
    transparency as a feature.
    """
    h, w = image.shape[:2]
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    fx = (xs - x0).astype(np.float32)[..., None]
    fy = (ys - y0).astype(np.float32)[..., None]
    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y1, 0, h - 1)
    img_f = image.astype(np.float32)
    v00 = img_f[y0c, x0c]
    v01 = img_f[y0c, x1c]
    v10 = img_f[y1c, x0c]
    v11 = img_f[y1c, x1c]
    v0 = v00 * (1.0 - fx) + v01 * fx
    v1 = v10 * (1.0 - fx) + v11 * fx
    blended = v0 * (1.0 - fy) + v1 * fy
    in_bounds = (xs >= 0) & (xs <= w - 1) & (ys >= 0) & (ys <= h - 1)
    blended[~in_bounds] = 0.0
    return np.clip(blended, 0.0, 255.0).astype(np.uint8)


def _check_image(image: np.ndarray) -> None:
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )


def _check_radius(radius: float) -> float:
    r = float(radius)
    if r < 0:
        raise ValueError(f"radius must be >= 0, got {r}")
    if r > MAX_RADIUS:
        raise ValueError(f"radius must be <= {MAX_RADIUS}, got {r}")
    return r
