"""Pure-math helpers for a hue-ring + saturation/value-triangle picker.

The classic Photoshop / MediBang colour picker is an outer hue ring
with an inner SV (saturation / value) triangle that rotates with the
selected hue. This module owns the geometry — hit testing, region
classification, and forward / inverse colour conversions — so the
widget can stay slim.

Coordinate convention
---------------------

The picker is normalised: the centre is at ``(0, 0)`` and both the
ring and triangle inscribe inside a unit circle (radius 1). The Qt
widget then scales by its current pixel size before painting and
hit-testing. Keeping the geometry unit-less makes the math testable
without a display server.
"""
from __future__ import annotations

import colorsys
import math

DEFAULT_RING_INNER = 0.78
DEFAULT_RING_OUTER = 1.0
TRIANGLE_INSCRIBED_RADIUS = 0.74

REGION_RING = "ring"
REGION_TRIANGLE = "triangle"
REGION_OUTSIDE = "outside"


# ---------------------------------------------------------------------------
# Region classification
# ---------------------------------------------------------------------------


def classify_region(
    point: tuple[float, float],
    *,
    ring_inner: float = DEFAULT_RING_INNER,
    ring_outer: float = DEFAULT_RING_OUTER,
) -> str:
    """Return which sub-region of the picker ``point`` falls in.

    * ``REGION_RING`` if the radius is between ``ring_inner`` and
      ``ring_outer``;
    * ``REGION_TRIANGLE`` if it's inside the inscribed triangle (the
      bounding circle is :data:`TRIANGLE_INSCRIBED_RADIUS`);
    * ``REGION_OUTSIDE`` otherwise.
    """
    if ring_inner <= 0 or ring_outer <= ring_inner:
        raise ValueError(
            f"ring_inner must be > 0 and < ring_outer, got "
            f"inner={ring_inner!r} outer={ring_outer!r}",
        )
    px, py = float(point[0]), float(point[1])
    radius = math.hypot(px, py)
    if ring_inner <= radius <= ring_outer:
        return REGION_RING
    # Triangle-inscribed circle is much smaller than the ring inner;
    # the cheap radius test rules out the corners between triangle
    # and ring.
    if radius <= TRIANGLE_INSCRIBED_RADIUS:
        return REGION_TRIANGLE
    return REGION_OUTSIDE


# ---------------------------------------------------------------------------
# Hue ↔ ring angle
# ---------------------------------------------------------------------------


def ring_angle_to_hue(angle_rad: float) -> float:
    """Convert a screen-space angle (radians, 0 = +x axis) to hue [0, 1).

    Angle increases counter-clockwise; we want hue 0 (red) at the
    top (12 o'clock) and progressing clockwise the way every
    standard colour wheel reads. The conversion folds the standard
    math convention into the visual one.
    """
    degrees = math.degrees(angle_rad)
    # Map (counter-clockwise from +x) to (clockwise from +y / top).
    visual = (90.0 - degrees) % 360.0
    return visual / 360.0


def hue_to_ring_angle(hue: float) -> float:
    """Inverse of :func:`ring_angle_to_hue`."""
    visual = (float(hue) % 1.0) * 360.0
    degrees = (90.0 - visual) % 360.0
    return math.radians(degrees)


def ring_position_for_hue(
    hue: float, *, radius: float = (DEFAULT_RING_INNER + DEFAULT_RING_OUTER) / 2.0,
) -> tuple[float, float]:
    """Cartesian position of the ring-cursor for a given hue."""
    angle = hue_to_ring_angle(hue)
    return (radius * math.cos(angle), radius * math.sin(angle))


# ---------------------------------------------------------------------------
# Triangle ↔ saturation / value
# ---------------------------------------------------------------------------


def triangle_vertices(
    hue: float,
    *,
    triangle_radius: float = TRIANGLE_INSCRIBED_RADIUS,
) -> tuple[
    tuple[float, float], tuple[float, float], tuple[float, float],
]:
    """Return the three vertices of the SV triangle for ``hue``.

    The triangle inscribes in a circle of ``triangle_radius`` and
    rotates so the saturated-hue corner points outward at the
    current hue's ring position. Vertex order is (saturated_hue,
    white, black) — matches MediBang's layout where pulling toward
    the corner shifts S/V accordingly.
    """
    base_angle = hue_to_ring_angle(hue)
    # Three vertices spaced 120° apart; rotate so the first one
    # lands at ``base_angle``.
    saturated = (
        triangle_radius * math.cos(base_angle),
        triangle_radius * math.sin(base_angle),
    )
    white_angle = base_angle + 2 * math.pi / 3
    white = (
        triangle_radius * math.cos(white_angle),
        triangle_radius * math.sin(white_angle),
    )
    black_angle = base_angle - 2 * math.pi / 3
    black = (
        triangle_radius * math.cos(black_angle),
        triangle_radius * math.sin(black_angle),
    )
    return (saturated, white, black)


def triangle_to_sv(
    point: tuple[float, float],
    hue: float,
    *,
    triangle_radius: float = TRIANGLE_INSCRIBED_RADIUS,
) -> tuple[float, float]:
    """Decode a triangle-relative ``point`` into ``(saturation, value)``.

    Uses barycentric coordinates: the saturated-hue / white / black
    corners sit at the triangle's three vertices, and the cursor's
    position along the corresponding edges decomposes into S and V.
    Out-of-triangle points are clamped to the nearest in-triangle
    location.
    """
    sat_pt, white_pt, black_pt = triangle_vertices(
        hue, triangle_radius=triangle_radius,
    )
    bx_sat, by_sat = sat_pt
    bx_white, by_white = white_pt
    bx_black, by_black = black_pt
    px, py = float(point[0]), float(point[1])
    a, b, c = _barycentric(
        (bx_sat, by_sat), (bx_white, by_white), (bx_black, by_black),
        (px, py),
    )
    # Clamp to a valid simplex.
    a = max(0.0, a)
    b = max(0.0, b)
    c = max(0.0, c)
    total = a + b + c
    if total <= 0:
        return (0.0, 0.0)
    a /= total
    b /= total
    c /= total
    # Saturation = how far the cursor is from the white corner (away
    # from b). Value = how far from the black corner (away from c).
    saturation = max(0.0, min(1.0, 1.0 - b))
    value = max(0.0, min(1.0, 1.0 - c))
    return (saturation, value)


def sv_to_triangle(
    saturation: float,
    value: float,
    hue: float,
    *,
    triangle_radius: float = TRIANGLE_INSCRIBED_RADIUS,
) -> tuple[float, float]:
    """Inverse — Cartesian position of the SV cursor for a given colour."""
    sat_pt, white_pt, black_pt = triangle_vertices(
        hue, triangle_radius=triangle_radius,
    )
    s = max(0.0, min(1.0, float(saturation)))
    v = max(0.0, min(1.0, float(value)))
    # Bary coords reverse-mapping: pick a barycentric mix where
    # b = 1 - s, c = 1 - v, a = s + v - 1 (clamped). The (1, 0, 0)
    # corner is fully saturated full-value; (0, 1, 0) is white; (0,
    # 0, 1) is black.
    a = max(0.0, s + v - 1.0)
    b = max(0.0, 1.0 - s)
    c = max(0.0, 1.0 - v)
    total = a + b + c
    if total <= 0:
        return (0.0, 0.0)
    a /= total
    b /= total
    c /= total
    return (
        a * sat_pt[0] + b * white_pt[0] + c * black_pt[0],
        a * sat_pt[1] + b * white_pt[1] + c * black_pt[1],
    )


# ---------------------------------------------------------------------------
# Compose: HSV ↔ RGB
# ---------------------------------------------------------------------------


def hsv_to_rgb(hue: float, saturation: float, value: float) -> tuple[int, int, int]:
    """Convert HSV [0, 1] → 8-bit RGB tuple."""
    r, g, b = colorsys.hsv_to_rgb(
        float(hue) % 1.0,
        max(0.0, min(1.0, float(saturation))),
        max(0.0, min(1.0, float(value))),
    )
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert 8-bit RGB → HSV [0, 1] tuple."""
    return colorsys.rgb_to_hsv(
        max(0, min(255, int(r))) / 255.0,
        max(0, min(255, int(g))) / 255.0,
        max(0, min(255, int(b))) / 255.0,
    )


# ---------------------------------------------------------------------------
# Internal — barycentric coordinates
# ---------------------------------------------------------------------------


def _barycentric(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    point: tuple[float, float],
) -> tuple[float, float, float]:
    """Barycentric coords of ``point`` against triangle ``p0 / p1 / p2``."""
    x, y = point
    x0, y0 = p0
    x1, y1 = p1
    x2, y2 = p2
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 1e-12:
        return (0.0, 0.0, 0.0)
    a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denom
    b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denom
    c = 1.0 - a - b
    return (a, b, c)
