"""Manga speed-line / focus-line generator.

Three stock manga FX patterns:

* **Radial** (``shuuchuusen`` / 集中線) — many thin lines radiating
  outward from a focus point. Used to direct the reader's eye toward
  a face or impact spot.
* **Parallel** (``ryuusen`` / 流線) — a band of parallel lines along
  one direction, suggesting motion blur or speed.
* **Burst** (``shuuchuu bakuhatsu`` / 集中爆発) — like radial but the
  lines start a short distance away from the centre, leaving a
  visible "hole" so the focus subject reads cleanly.

The pure-numpy ``render_speedlines`` returns a fresh HxWx4 RGBA
buffer ready to drop in as a layer. Density / length / jitter are
RNG-seeded so a recipe round-trips deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SPEEDLINE_KINDS = ("radial", "parallel", "burst")
DEFAULT_SPEEDLINE_KIND = "radial"

LINE_COUNT_MIN = 4
LINE_COUNT_MAX = 600
DEFAULT_LINE_COUNT = 80

LINE_THICKNESS_MIN = 1
LINE_THICKNESS_MAX = 16
DEFAULT_LINE_THICKNESS = 2

# Burst inner radius is a fraction of the outer canvas extent. A
# small radius hides the focus subject; a large radius makes the
# lines hug the rim only.
DEFAULT_BURST_RADIUS_RATIO = 0.25


@dataclass(frozen=True)
class SpeedlineOptions:
    """Frozen recipe for one speedline render — JSON-friendly."""

    kind: str = DEFAULT_SPEEDLINE_KIND
    count: int = DEFAULT_LINE_COUNT
    thickness: int = DEFAULT_LINE_THICKNESS
    color: tuple[int, int, int, int] = (0, 0, 0, 255)
    # Radial / burst — focus point in pixel space (defaults to canvas
    # centre when None). Parallel — used as anchor for line spacing.
    center: tuple[int, int] | None = None
    # Parallel — degrees CCW from horizontal.
    angle_deg: float = 0.0
    # Burst — inner radius as a fraction of the canvas's longest side.
    inner_radius_ratio: float = DEFAULT_BURST_RADIUS_RATIO
    # 0..1 — random length variation per line. 0 = uniform, 1 = up to
    # 100% of full length is randomly trimmed off.
    jitter: float = 0.4
    seed: int = 0

    def __post_init__(self) -> None:
        if self.kind not in SPEEDLINE_KINDS:
            raise ValueError(
                f"unknown kind {self.kind!r}; expected one of {SPEEDLINE_KINDS}",
            )
        if not LINE_COUNT_MIN <= int(self.count) <= LINE_COUNT_MAX:
            raise ValueError(
                f"count must be in [{LINE_COUNT_MIN}, {LINE_COUNT_MAX}],"
                f" got {self.count}",
            )
        if not LINE_THICKNESS_MIN <= int(self.thickness) <= LINE_THICKNESS_MAX:
            raise ValueError(
                f"thickness must be in [{LINE_THICKNESS_MIN}, "
                f"{LINE_THICKNESS_MAX}], got {self.thickness}",
            )
        if len(self.color) != 4 or any(
            not 0 <= int(c) <= 255 for c in self.color
        ):
            raise ValueError(
                f"color must be a 4-tuple of 0..255 ints, got {self.color!r}",
            )
        if not 0.0 <= float(self.inner_radius_ratio) < 1.0:
            raise ValueError(
                f"inner_radius_ratio must be in [0, 1), got "
                f"{self.inner_radius_ratio}",
            )
        if not 0.0 <= float(self.jitter) <= 1.0:
            raise ValueError(f"jitter must be in [0, 1], got {self.jitter}")


def render_speedlines(
    canvas_shape: tuple[int, int],
    options: SpeedlineOptions,
) -> np.ndarray:
    """Return a fresh HxWx4 uint8 RGBA buffer with the speedlines drawn.

    ``canvas_shape`` is ``(height, width)``. The returned buffer is
    fully transparent everywhere except along the rendered lines.
    """
    h, w = canvas_shape
    if h <= 0 or w <= 0:
        raise ValueError(
            f"canvas_shape must be positive, got {canvas_shape!r}",
        )
    out = np.zeros((h, w, 4), dtype=np.uint8)
    rng = np.random.default_rng(int(options.seed))
    if options.kind in ("radial", "burst"):
        _render_radial(out, options, rng, burst=options.kind == "burst")
    elif options.kind == "parallel":
        _render_parallel(out, options, rng)
    return out


def _render_radial(
    out: np.ndarray,
    options: SpeedlineOptions,
    rng: np.random.Generator,
    *,
    burst: bool,
) -> None:
    h, w = out.shape[:2]
    cx, cy = options.center if options.center is not None else (w // 2, h // 2)
    cx_f = float(cx)
    cy_f = float(cy)
    diag = float(max(h, w))
    inner = float(options.inner_radius_ratio) * diag if burst else 0.0
    outer = diag * 1.1   # extend past corners so radial reach the edge
    angles = rng.uniform(0.0, 2.0 * np.pi, size=int(options.count))
    jitter = float(options.jitter)
    for theta in angles:
        trim = rng.uniform(0.0, jitter * (outer - inner))
        r1 = inner
        r2 = outer - trim
        if r2 <= r1:
            continue
        x1 = cx_f + r1 * np.cos(theta)
        y1 = cy_f + r1 * np.sin(theta)
        x2 = cx_f + r2 * np.cos(theta)
        y2 = cy_f + r2 * np.sin(theta)
        _draw_line(
            out, x1, y1, x2, y2,
            color=options.color,
            thickness=int(options.thickness),
        )


def _render_parallel(
    out: np.ndarray,
    options: SpeedlineOptions,
    rng: np.random.Generator,
) -> None:
    h, w = out.shape[:2]
    cx, cy = options.center if options.center is not None else (w // 2, h // 2)
    cx_f = float(cx)
    cy_f = float(cy)
    rad = np.radians(float(options.angle_deg))
    dx = float(np.cos(rad))
    dy = float(np.sin(rad))
    nx = -dy
    ny = dx
    diag = float(np.hypot(h, w))
    half = diag * 0.6
    spacing = max(1.0, diag / float(options.count))
    jitter = float(options.jitter)
    for i in range(int(options.count)):
        offset = (i - options.count / 2.0) * spacing
        anchor_x = cx_f + nx * offset
        anchor_y = cy_f + ny * offset
        trim_back = rng.uniform(0.0, jitter * 2.0 * half)
        x1 = anchor_x - dx * (half - trim_back / 2.0)
        y1 = anchor_y - dy * (half - trim_back / 2.0)
        x2 = anchor_x + dx * (half - trim_back / 2.0)
        y2 = anchor_y + dy * (half - trim_back / 2.0)
        _draw_line(
            out, x1, y1, x2, y2,
            color=options.color,
            thickness=int(options.thickness),
        )


def _draw_line(
    out: np.ndarray,
    x1: float, y1: float, x2: float, y2: float,
    *,
    color: tuple[int, int, int, int],
    thickness: int,
) -> None:
    """Bresenham-style line rasteriser with thickness via square stamp."""
    h, w = out.shape[:2]
    dx = x2 - x1
    dy = y2 - y1
    steps = int(max(abs(dx), abs(dy))) + 1
    if steps < 1:
        return
    xs = np.linspace(x1, x2, steps)
    ys = np.linspace(y1, y2, steps)
    half = max(0, thickness // 2)
    for px, py in zip(xs, ys, strict=True):
        ix = int(round(px))
        iy = int(round(py))
        x_lo = max(0, ix - half)
        x_hi = min(w, ix + half + 1)
        y_lo = max(0, iy - half)
        y_hi = min(h, iy + half + 1)
        if x_lo >= x_hi or y_lo >= y_hi:
            continue
        out[y_lo:y_hi, x_lo:x_hi, 0] = int(color[0])
        out[y_lo:y_hi, x_lo:x_hi, 1] = int(color[1])
        out[y_lo:y_hi, x_lo:x_hi, 2] = int(color[2])
        out[y_lo:y_hi, x_lo:x_hi, 3] = int(color[3])
