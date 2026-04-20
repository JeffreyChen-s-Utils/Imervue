"""
Tone curve — Lightroom-style RGB/per-channel curve.

Given a list of control points (x, y) in [0, 1] the curve is expanded
to a 256-entry uint8 lookup table using monotone cubic interpolation
(Fritsch-Carlson), then applied to each channel. A default empty curve
is the identity.

Control points are a list of ``(input, output)`` pairs, both in ``[0.0, 1.0]``.
The endpoints ``(0.0, 0.0)`` and ``(1.0, 1.0)`` are implicit if absent and
are always added before interpolation so the curve is well-defined at the
boundaries.

Per-channel curves are supported via :func:`build_lut_rgb` — pass four
lists of points (rgb, r, g, b); the rgb curve applies first, then each
channel curve stacks on top.
"""
from __future__ import annotations

import numpy as np

_LUT_SIZE = 256
_IDENTITY_LUT: np.ndarray = np.arange(_LUT_SIZE, dtype=np.uint8)


def is_identity_points(points: list[tuple[float, float]]) -> bool:
    """Return True when the control points describe a straight diagonal."""
    if not points:
        return True
    xs, ys = zip(*points)
    if len(xs) != len(ys):
        return False
    return all(abs(x - y) < 1e-6 for x, y in zip(xs, ys))


def _normalise_points(
    points: list[tuple[float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    """Clamp, sort, and add implicit endpoints, returning monotonic xs, ys."""
    pts = [(float(x), float(y)) for x, y in points]
    pts = [(max(0.0, min(1.0, x)), max(0.0, min(1.0, y))) for x, y in pts]
    have_start = any(abs(x) < 1e-6 for x, _ in pts)
    have_end = any(abs(x - 1.0) < 1e-6 for x, _ in pts)
    if not have_start:
        pts.append((0.0, 0.0))
    if not have_end:
        pts.append((1.0, 1.0))
    pts.sort(key=lambda p: p[0])
    # Collapse duplicate xs by keeping the last y.
    collapsed: dict[float, float] = {}
    for x, y in pts:
        collapsed[x] = y
    xs = np.array(sorted(collapsed.keys()), dtype=np.float64)
    ys = np.array([collapsed[x] for x in xs], dtype=np.float64)
    return xs, ys


def _monotone_cubic_tangents(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Fritsch-Carlson monotone cubic tangents at each knot."""
    n = len(xs)
    if n < 2:
        return np.zeros_like(xs)
    deltas = np.diff(ys) / np.diff(xs)
    tangents = np.empty(n, dtype=np.float64)
    tangents[0] = deltas[0]
    tangents[-1] = deltas[-1]
    for i in range(1, n - 1):
        if deltas[i - 1] * deltas[i] <= 0:
            tangents[i] = 0.0
        else:
            tangents[i] = 0.5 * (deltas[i - 1] + deltas[i])
    # Enforce monotonicity.
    for i in range(n - 1):
        d = deltas[i]
        if abs(d) < 1e-12:
            tangents[i] = 0.0
            tangents[i + 1] = 0.0
            continue
        a = tangents[i] / d
        b = tangents[i + 1] / d
        s = a * a + b * b
        if s > 9.0:
            t = 3.0 / np.sqrt(s)
            tangents[i] = t * a * d
            tangents[i + 1] = t * b * d
    return tangents


def build_lut(points: list[tuple[float, float]]) -> np.ndarray:
    """Build a 256-entry uint8 lookup table from control points."""
    if is_identity_points(points):
        return _IDENTITY_LUT
    xs, ys = _normalise_points(points)
    if len(xs) == 2:
        # Fast-path for a straight two-point curve.
        grid = np.linspace(0.0, 1.0, _LUT_SIZE)
        out = np.interp(grid, xs, ys)
    else:
        tangents = _monotone_cubic_tangents(xs, ys)
        grid = np.linspace(0.0, 1.0, _LUT_SIZE)
        out = np.empty_like(grid)
        idx = np.clip(np.searchsorted(xs, grid) - 1, 0, len(xs) - 2)
        for i, k in enumerate(idx):
            h = xs[k + 1] - xs[k]
            if h <= 0:
                out[i] = ys[k]
                continue
            t = (grid[i] - xs[k]) / h
            h00 = (1 + 2 * t) * (1 - t) ** 2
            h10 = t * (1 - t) ** 2
            h01 = t ** 2 * (3 - 2 * t)
            h11 = t ** 2 * (t - 1)
            out[i] = (
                h00 * ys[k]
                + h10 * h * tangents[k]
                + h01 * ys[k + 1]
                + h11 * h * tangents[k + 1]
            )
    np.clip(out, 0.0, 1.0, out=out)
    return (out * 255.0 + 0.5).astype(np.uint8)


def apply_tone_curve(
    arr: np.ndarray,
    rgb_points: list[tuple[float, float]],
    r_points: list[tuple[float, float]] | None = None,
    g_points: list[tuple[float, float]] | None = None,
    b_points: list[tuple[float, float]] | None = None,
) -> np.ndarray:
    """Apply an RGB curve (and optional per-channel curves) to an RGBA uint8 array."""
    if (
        is_identity_points(rgb_points)
        and is_identity_points(r_points or [])
        and is_identity_points(g_points or [])
        and is_identity_points(b_points or [])
    ):
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_tone_curve expects HxWx4 RGBA uint8")
    rgb_lut = build_lut(rgb_points)
    r_lut = build_lut(r_points or [])
    g_lut = build_lut(g_points or [])
    b_lut = build_lut(b_points or [])
    out = arr.copy()
    # Stack RGB curve first so per-channel curves layer on top.
    channels = out[..., :3]
    channels = rgb_lut[channels]
    channels[..., 0] = r_lut[channels[..., 0]]
    channels[..., 1] = g_lut[channels[..., 1]]
    channels[..., 2] = b_lut[channels[..., 2]]
    out[..., :3] = channels
    return out
