"""Shared coordinates and curves for the Blender model of Imeru.

The model is built in canvas pixels of the 1024 x 1536 puppet canvas (x right, y down) plus
a depth toward the viewer, and converted to Blender world units here: 1 unit = ``PX`` pixels,
the canvas centre at the origin, the camera looking along +Y, so depth toward the viewer is
world -Y. Everything else in this package thinks in pixels.
"""
from __future__ import annotations

import math

from mathutils import Vector

W, H = 1024, 1536
CX = W / 2
PX = 1000.0


def px(x: float, y: float, depth: float = 0.0) -> Vector:
    """Canvas pixel (x, y) at *depth* toward the viewer, as a world position."""
    return Vector(((x - W / 2) / PX, -depth / PX, (H / 2 - y) / PX))


def to_px(v: Vector) -> tuple[float, float, float]:
    """A world position back to (x, y, depth) canvas pixels."""
    return v.x * PX + W / 2, H / 2 - v.z * PX, -v.y * PX


def bez(p0, c0, c1, p1, n: int = 24) -> list[tuple[float, ...]]:
    """Points along a cubic Bézier curve; points may be (x, y) or (x, y, depth)."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        corners = zip(p0, c0, c1, p1, strict=True)
        out.append(tuple(a * p + b * q + c * r + d * s for p, q, r, s in corners))
    return out


def chain(*parts) -> list[tuple[float, ...]]:
    """Concatenate point lists, dropping a repeated joint point."""
    out: list[tuple[float, ...]] = []
    for part in parts:
        points = list(part)
        if out and all(abs(a - b) < 1e-6 for a, b in zip(out[-1], points[0], strict=True)):
            points = points[1:]
        out.extend(points)
    return out


def mirror(points) -> list[tuple[float, ...]]:
    """Points mirrored about the canvas centre line."""
    return [(W - p[0], *p[1:]) for p in points]


def resample(points, n: int) -> list[tuple[float, ...]]:
    """*n* points evenly spaced along a polyline."""
    pts = [tuple(p) for p in points]
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:], strict=False)]
    total = sum(seg) or 1.0
    out, acc, k = [], 0.0, 0
    for i in range(n):
        target = total * i / (n - 1)
        while k < len(seg) - 1 and acc + seg[k] < target:
            acc += seg[k]
            k += 1
        t = 0.0 if seg[k] == 0 else min(1.0, (target - acc) / seg[k])
        out.append(tuple(a + (b - a) * t for a, b in zip(pts[k], pts[k + 1], strict=True)))
    return out


def hexrgb(colour: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    """A ``#RRGGBB`` sRGB colour as linear RGBA, which is what Blender's colour sockets take."""
    h = colour.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, alpha)


def scatter(index: int, salt: int = 0) -> float:
    """A value in [0, 1) that looks random but is fixed by *index* and *salt*.

    A low-discrepancy (golden-ratio) sequence: neighbouring indices land far apart, the
    values cover the range evenly, and every build of the model gets the same ones.
    """
    return ((index + 1) * 0.6180339887498949 + salt * 0.7548776662466927) % 1.0


def smoothstep(e0: float, e1: float, x: float) -> float:
    """Hermite step from 0 at *e0* to 1 at *e1*."""
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)
