"""Stroke-based oil painting: repaint an image with curved brush strokes, coarse to fine.

The method is Hertzmann's (*Painterly Rendering with Curved Brush Strokes of Multiple Sizes*,
SIGGRAPH 1998): for each brush size, from the largest, the image is blurred to that size and
compared with the canvas so far; wherever a grid cell strays from it by more than a threshold,
a stroke is laid from the cell's worst pixel (the largest brush covers every cell, so the whole
canvas is painted and no bare ground is left), its colour taken there, its path turning along
the image's edges (across the luminance gradient) until the colour under it stops matching.
Large strokes block the picture in, small ones only go where detail is.

Every stroke is laid with :class:`Imervue.paint.brush_engine.BrushStroke`, the engine behind the
Paint workspace's brushes. Two things make the result read as oil rather than as a filter:

* **Bristles** — the direction of the last stroke over each pixel is kept, and a fine noise is
  smeared along that field (line-integral convolution), so every stroke carries the streaks of
  its brush.
* **Impasto** — the bristle streaks, heavier where the paint is light, are taken as the paint's
  height and lit from the upper left, so the strokes stand off the canvas.

Pure NumPy and SciPy, deterministic for a given ``seed``; no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from Imervue.image.local_contrast import gaussian_plane
from Imervue.paint.brush_engine import BrushStroke, BrushStrokeOptions

LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)
# The screen light the impasto is lit by: from the upper left, as a painter's north light.
LIGHT = (-0.6, -0.8)
# Steps (px) the bristle streaks are smeared along each way, and how coarse their noise is.
BRISTLE_STEPS = 10
BRISTLE_GRAIN = 1.2
# A grid cell under this share of importance counts as that much, so the background still gets
# its broad strokes where no importance is given.
IMPORTANCE_FLOOR = 0.15


@dataclass(frozen=True)
class PainterlyOptions:
    """How :func:`paint` paints.

    ``radii`` are the brush radii in px, largest first; ``threshold`` is the mean colour error
    (the sum of the RGB differences, 0..765) a grid cell may keep before a stroke is laid there.
    ``blur_factor`` blurs each brush's reference by that share of its radius; grid cells are
    ``grid_factor`` of the radius across; a stroke runs ``min_length`` to ``max_length`` control
    points; ``curvature`` is how much of each turn it takes (1: all, 0: straight on);
    ``color_jitter`` lets each dab's colour wander in HSV; ``bristle`` and ``impasto`` set how
    strong the brush streaks and the paint's relief are (0: none); ``ground`` is the canvas's
    first colour (None: the image's mean).
    """

    radii: tuple[int, ...] = (16, 8, 4, 2)
    threshold: float = 24.0
    blur_factor: float = 0.5
    grid_factor: float = 1.0
    min_length: int = 3
    max_length: int = 12
    curvature: float = 0.6
    opacity: float = 0.92
    hardness: float = 0.5
    color_jitter: float = 0.015
    bristle: float = 0.10
    impasto: float = 0.25
    ground: tuple[int, int, int] | None = None
    seed: int = 0


def paint(image: np.ndarray, options: PainterlyOptions | None = None, *,
          importance: np.ndarray | None = None) -> np.ndarray:
    """``image`` (HxWx3 or HxWx4 uint8) repainted in oil; returns HxWx3 uint8.

    ``importance`` (HxW, 0..1), when given, lowers the threshold where it is high, so a face
    gets its fine strokes and a background keeps its broad ones; the largest brush ignores it.
    An alpha channel is ignored: composite the image over its background first.
    """
    options = options or PainterlyOptions()
    source = _check_image(image)
    _check_options(options)
    weight = _importance(importance, source.shape[:2])
    rng = np.random.default_rng(options.seed)
    canvas = _ground(source, options)
    direction = np.zeros(source.shape[:2] + (2,), dtype=np.float32)
    for layer, radius in enumerate(options.radii):
        sigma = radius * options.blur_factor
        reference = _blurred(source, sigma)
        layer_weight = None if layer == 0 else weight
        _paint_layer(canvas, reference, radius, options, rng, direction, weight=layer_weight,
                     cover=layer == 0)
    return _finish(canvas[..., :3], direction, options, rng)


# ---------------------------------------------------------------------------
# Layers and strokes
# ---------------------------------------------------------------------------


def _paint_layer(canvas: np.ndarray, reference: np.ndarray, radius: int,
                 options: PainterlyOptions, rng: np.random.Generator, direction: np.ndarray, *,
                 weight: np.ndarray | None, cover: bool = False) -> None:
    """Lay one brush size's strokes where the canvas strays from ``reference`` (all over if
    ``cover``)."""
    lum = reference @ LUMA
    gx, gy = _sobel(lum, axis=1), _sobel(lum, axis=0)
    error = np.abs(canvas[..., :3].astype(np.float32) - reference).sum(axis=2)
    step = max(1, round(radius * options.grid_factor))
    h, w = error.shape
    cells = [(x, y) for y in range(0, h, step) for x in range(0, w, step)]
    for index in rng.permutation(len(cells)):
        x, y = cells[index]
        block = error[y:y + step, x:x + step]
        limit = options.threshold
        if weight is not None:
            limit /= max(IMPORTANCE_FLOOR, float(weight[y:y + step, x:x + step].mean()))
        if not cover and block.mean() <= limit:
            continue
        by, bx = np.unravel_index(int(np.argmax(block)), block.shape)
        start = (float(x + bx), float(y + by))
        path = _stroke_path(canvas, reference, (gx, gy), start, radius, options)
        _lay(canvas, path, reference[y + by, x + bx], radius, options, rng, direction)


def _stroke_path(canvas: np.ndarray, reference: np.ndarray,
                 gradient: tuple[np.ndarray, np.ndarray], start: tuple[float, float],
                 radius: int, options: PainterlyOptions) -> list[tuple[float, float]]:
    """One stroke's control points from ``start``: along the edges until its colour stops
    fitting."""
    gx, gy = gradient
    h, w = gx.shape
    x, y = start
    colour = reference[int(y), int(x)]
    path = [(x, y)]
    last = (0.0, 0.0)
    for _ in range(options.max_length):
        ix, iy = int(x), int(y)
        if len(path) > options.min_length and _strays(canvas, reference, colour, ix, iy):
            break
        turn = _edge_direction(gx[iy, ix], gy[iy, ix], last, options.curvature)
        if turn is None:
            break
        x, y = x + radius * turn[0], y + radius * turn[1]
        if not (0.0 <= x < w and 0.0 <= y < h):
            break
        last = turn
        path.append((x, y))
    return path


def _strays(canvas: np.ndarray, reference: np.ndarray, colour: np.ndarray, x: int, y: int) -> bool:
    """Whether the stroke's colour fits the reference at (x, y) worse than the canvas does."""
    wanted = np.abs(reference[y, x] - colour).sum()
    painted = np.abs(canvas[y, x, :3].astype(np.float32) - colour).sum()
    return bool(wanted > painted)


def _edge_direction(gx: float, gy: float, last: tuple[float, float],
                    curvature: float) -> tuple[float, float] | None:
    """The unit step along the edge (across the gradient), turned no more than ``curvature``
    allows."""
    dx, dy = -float(gy), float(gx)
    length = np.hypot(dx, dy)
    if length < 1e-3:
        return None
    dx, dy = dx / length, dy / length
    if last[0] * dx + last[1] * dy < 0.0:
        dx, dy = -dx, -dy
    if last != (0.0, 0.0):
        dx = curvature * dx + (1.0 - curvature) * last[0]
        dy = curvature * dy + (1.0 - curvature) * last[1]
        length = max(float(np.hypot(dx, dy)), 1e-6)
        dx, dy = dx / length, dy / length
    return dx, dy


def _lay(canvas: np.ndarray, path: list[tuple[float, float]], colour: np.ndarray, radius: int,
         options: PainterlyOptions, rng: np.random.Generator, direction: np.ndarray) -> None:
    """Paint ``path`` with the brush engine and note its direction under it."""
    stroke = BrushStroke(BrushStrokeOptions(
        color=tuple(int(c) for c in np.clip(colour + 0.5, 0, 255)), size=max(1, 2 * radius),
        opacity=options.opacity, hardness=options.hardness, kind="pen",
        seed=int(rng.integers(1 << 31)), color_jitter=options.color_jitter, taper_start_dabs=2,
    ))
    stroke.begin(canvas, *path[0])
    for point in path[1:]:
        stroke.extend(canvas, *point)
    stroke.end(canvas, *path[-1])
    _note_direction(direction, path, radius)


def _note_direction(direction: np.ndarray, path: list[tuple[float, float]], radius: int) -> None:
    """Write each segment's unit direction over the brush's disc along it (the last stroke
    wins)."""
    h, w = direction.shape[:2]
    for (x0, y0), (x1, y1) in zip(path, path[1:], strict=False):
        dx, dy = x1 - x0, y1 - y0
        length = float(np.hypot(dx, dy))
        if length < 1e-6:
            continue
        top, bottom = max(0, int(min(y0, y1)) - radius), min(h, int(max(y0, y1)) + radius + 1)
        left, right = max(0, int(min(x0, x1)) - radius), min(w, int(max(x0, x1)) + radius + 1)
        if top >= bottom or left >= right:
            continue
        ys, xs = np.mgrid[top:bottom, left:right].astype(np.float32)
        along = np.clip(((xs - x0) * dx + (ys - y0) * dy) / (length * length), 0.0, 1.0)
        near = np.hypot(xs - (x0 + along * dx), ys - (y0 + along * dy)) <= radius
        direction[top:bottom, left:right][near] = (dx / length, dy / length)


# ---------------------------------------------------------------------------
# Bristles and impasto
# ---------------------------------------------------------------------------


def _finish(paint_rgb: np.ndarray, direction: np.ndarray, options: PainterlyOptions,
            rng: np.random.Generator) -> np.ndarray:
    """The painted canvas with its bristle streaks and its impasto lit."""
    if options.bristle <= 0.0 and options.impasto <= 0.0:
        return paint_rgb.copy()
    rgb = paint_rgb.astype(np.float32)
    noise = gaussian_plane(rng.random(rgb.shape[:2], dtype=np.float32), BRISTLE_GRAIN)
    streaks = _smear(noise, direction)
    streaks = (streaks - streaks.mean()) / max(float(streaks.std()), 1e-6)
    lightness = (rgb @ LUMA) / 255.0
    height = streaks * (0.5 + lightness)               # light paint is laid thicker
    shade = (_sobel(height, axis=1) * LIGHT[0]
             + _sobel(height, axis=0) * LIGHT[1]) / 8.0
    out = (rgb * (1.0 + options.bristle * 0.25 * streaks[..., None])
           + options.impasto * 40.0 * shade[..., None])
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def _smear(noise: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """``noise`` averaged along the direction field, both ways (line-integral convolution)."""
    h, w = noise.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    total = noise.copy()
    for sign in (1.0, -1.0):
        px, py = xs.copy(), ys.copy()
        for _ in range(BRISTLE_STEPS):
            ix = np.clip(px.astype(np.int32), 0, w - 1)
            iy = np.clip(py.astype(np.int32), 0, h - 1)
            px += sign * direction[iy, ix, 0]
            py += sign * direction[iy, ix, 1]
            sx = np.clip(px.astype(np.int32), 0, w - 1)
            sy = np.clip(py.astype(np.int32), 0, h - 1)
            total += noise[sy, sx]
    return total / (2 * BRISTLE_STEPS + 1)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def _blurred(image: np.ndarray, sigma: float) -> np.ndarray:
    """``image`` (HxWxC) blurred at ``sigma`` across its plane, each channel apart."""
    return np.stack(
        [gaussian_plane(image[..., channel], sigma) for channel in range(image.shape[2])],
        axis=2,
    )


def _sobel(plane: np.ndarray, axis: int) -> np.ndarray:
    """The Sobel derivative of ``plane`` along ``axis`` (1 across, 0 down), the edges mirrored."""
    padded = np.pad(plane.astype(np.float32), 1, mode="symmetric")
    if axis == 1:
        step = padded[:, 2:] - padded[:, :-2]
        return step[:-2] + 2.0 * step[1:-1] + step[2:]
    step = padded[2:] - padded[:-2]
    return step[:, :-2] + 2.0 * step[:, 1:-1] + step[:, 2:]


def _check_image(image: np.ndarray) -> np.ndarray:
    if image.ndim != 3 or image.shape[2] not in (3, 4) or image.dtype != np.uint8:
        raise ValueError(f"image must be HxWx3 or HxWx4 uint8, got {image.shape} {image.dtype}")
    if min(image.shape[:2]) < 2:
        raise ValueError(f"image is too small to paint: {image.shape[:2]}")
    return image[..., :3].astype(np.float32)


def _check_options(options: PainterlyOptions) -> None:
    radii = options.radii
    if not radii or any(r < 1 for r in radii) or list(radii) != sorted(radii, reverse=True):
        raise ValueError(f"radii must be positive and largest first, got {radii}")
    if options.threshold <= 0.0 or options.max_length < 1 or options.min_length < 0:
        raise ValueError("threshold must be positive, max_length at least 1, min_length >= 0")
    if not 0.0 <= options.curvature <= 1.0:
        raise ValueError(f"curvature must be within 0..1, got {options.curvature}")


def _importance(importance: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray | None:
    if importance is None:
        return None
    if importance.shape != shape:
        raise ValueError(f"importance must be {shape}, got {importance.shape}")
    return np.clip(importance.astype(np.float32), 0.0, 1.0)


def _ground(source: np.ndarray, options: PainterlyOptions) -> np.ndarray:
    if options.ground is not None:
        colour = np.array(options.ground, dtype=np.float32)
    else:
        colour = source.reshape(-1, 3).mean(axis=0)
    canvas = np.empty(source.shape[:2] + (4,), dtype=np.uint8)
    canvas[..., :3] = np.clip(colour + 0.5, 0, 255).astype(np.uint8)
    canvas[..., 3] = 255
    return canvas
