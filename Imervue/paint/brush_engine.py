"""Pure-numpy brush rasterisation for the Paint workspace.

Three layers:

* :func:`round_brush_kernel` — builds an ``(N, N)`` float32 alpha kernel
  in ``[0, 1]`` with a hardness-controlled radial falloff. The kernel is
  the per-pixel coverage that the brush deposits in a single dab.
* :func:`apply_dab` — composites one kernel into an HxWx4 RGBA uint8
  canvas at integer ``(cx, cy)`` using the requested blend mode.
* :class:`BrushStroke` — accumulates pointer positions and stamps dabs
  along straight-line interpolation between successive samples so a
  fast cursor doesn't leave gaps.

The module is Qt-free so the rasterisation can be unit-tested without
a display server. The Paint workspace's tool dispatcher feeds it
PointerEvents and reads back a damaged-rect that the canvas can use to
schedule a partial repaint.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# Kernel construction
# ---------------------------------------------------------------------------

KERNEL_SIZE_MIN = 1
KERNEL_SIZE_MAX = 1024


def round_brush_kernel(size: int, hardness: float) -> np.ndarray:
    """Return an ``(N, N)`` float32 alpha kernel, normalised to ``[0, 1]``.

    ``hardness`` in ``[0, 1]`` controls the inner-radius plateau:

    * ``hardness == 1`` — fully solid disc (1.0 inside the radius, 0 outside)
    * ``hardness == 0`` — pure radial gradient peaking at the centre
    * intermediate values — solid out to ``hardness * radius`` then a
      smooth-step falloff to the edge

    ``size`` is clamped to :data:`KERNEL_SIZE_MIN`..:data:`KERNEL_SIZE_MAX`
    so callers can pass slider values without re-validating.
    """
    size = max(KERNEL_SIZE_MIN, min(KERNEL_SIZE_MAX, int(size)))
    hardness = max(0.0, min(1.0, float(hardness)))
    if size == 1:
        return np.array([[1.0]], dtype=np.float32)

    radius = (size - 1) / 2.0
    yy, xx = np.indices((size, size), dtype=np.float32)
    cx = cy = radius
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    if hardness >= 1.0:
        kernel = np.where(dist <= radius, 1.0, 0.0)
    else:
        inner = max(0.0, hardness) * radius
        if inner >= radius:
            kernel = np.where(dist <= radius, 1.0, 0.0)
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.clip((dist - inner) / max(1e-6, radius - inner), 0.0, 1.0)
            falloff = 1.0 - (t * t * (3.0 - 2.0 * t))   # smooth-step
            kernel = np.where(dist <= radius, falloff, 0.0)

    return kernel.astype(np.float32, copy=False)


# ---------------------------------------------------------------------------
# Dab compositing
# ---------------------------------------------------------------------------

BLEND_MODES = (
    "normal", "multiply", "screen", "overlay",
    "darken", "lighten",
    "color_dodge", "color_burn",
    "soft_light", "hard_light",
    "linear_burn", "linear_dodge",
)


@dataclass(frozen=True)
class DabResult:
    """Damage rectangle (x, y, w, h) describing what changed in the canvas."""

    x: int
    y: int
    w: int
    h: int

    @property
    def is_empty(self) -> bool:
        return self.w <= 0 or self.h <= 0


def apply_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    color: tuple[int, int, int],
    *,
    opacity: float = 1.0,
    blend_mode: str = "normal",
) -> DabResult:
    """Composite ``kernel * color`` into ``canvas`` at ``(cx, cy)`` in-place.

    ``canvas`` must be HxWx4 uint8 RGBA. Returns the damaged rectangle so
    the caller can schedule a localised repaint.
    """
    _check_canvas(canvas)
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")
    if blend_mode not in BLEND_MODES:
        raise ValueError(
            f"unknown blend_mode {blend_mode!r}; expected one of {BLEND_MODES}",
        )
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return DabResult(0, 0, 0, 0)

    kh, kw = kernel.shape
    half_w = kw // 2
    half_h = kh // 2
    x0 = int(round(cx)) - half_w
    y0 = int(round(cy)) - half_h
    x1 = x0 + kw
    y1 = y0 + kh

    h, w = canvas.shape[:2]
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(w, x1)
    cy1 = min(h, y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return DabResult(0, 0, 0, 0)

    kx0 = cx0 - x0
    ky0 = cy0 - y0
    kx1 = kx0 + (cx1 - cx0)
    ky1 = ky0 + (cy1 - cy0)

    dst_view = canvas[cy0:cy1, cx0:cx1]
    k = kernel[ky0:ky1, kx0:kx1] * opacity   # alpha for this dab
    fg = np.array(color, dtype=np.float32)
    _composite_in_place(dst_view, k, fg, blend_mode)
    return DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0)


def _composite_in_place(
    dst: np.ndarray, alpha: np.ndarray, fg_color: np.ndarray, blend_mode: str,
) -> None:
    """Apply ``alpha``-weighted blend of ``fg_color`` onto the RGBA ``dst``."""
    bg = dst[..., :3].astype(np.float32) / 255.0
    fg = np.broadcast_to(fg_color[None, None, :3] / 255.0, bg.shape).copy()
    blended = _blend_rgb(bg, fg, blend_mode)

    a = alpha[..., None]
    out_rgb = bg * (1.0 - a) + blended * a
    dst[..., :3] = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    # Alpha channel — accumulate paint coverage in the dst alpha.
    dst_a = dst[..., 3].astype(np.float32) / 255.0
    new_a = dst_a + (1.0 - dst_a) * alpha
    dst[..., 3] = np.clip(new_a * 255.0, 0.0, 255.0).astype(np.uint8)


def _blend_rgb(bg: np.ndarray, fg: np.ndarray, mode: str) -> np.ndarray:
    """Per-pixel blend of two ``[0, 1]`` RGB arrays."""
    if mode == "normal":
        return fg
    if mode == "multiply":
        return bg * fg
    if mode == "screen":
        return 1.0 - (1.0 - bg) * (1.0 - fg)
    if mode == "overlay":
        return np.where(bg <= 0.5, 2.0 * bg * fg, 1.0 - 2.0 * (1.0 - bg) * (1.0 - fg))
    if mode == "darken":
        return np.minimum(bg, fg)
    if mode == "lighten":
        return np.maximum(bg, fg)
    if mode == "color_dodge":
        return np.where(fg >= 1.0, 1.0, np.minimum(1.0, bg / np.maximum(1.0 - fg, 1e-6)))
    if mode == "color_burn":
        return np.where(fg <= 0.0, 0.0, 1.0 - np.minimum(1.0, (1.0 - bg) / np.maximum(fg, 1e-6)))
    if mode == "soft_light":
        return np.where(
            fg <= 0.5,
            bg - (1.0 - 2.0 * fg) * bg * (1.0 - bg),
            bg + (2.0 * fg - 1.0) * (_d_curve(bg) - bg),
        )
    if mode == "hard_light":
        return np.where(fg <= 0.5, 2.0 * bg * fg, 1.0 - 2.0 * (1.0 - bg) * (1.0 - fg))
    if mode == "linear_burn":
        return np.maximum(bg + fg - 1.0, 0.0)
    if mode == "linear_dodge":
        return np.minimum(bg + fg, 1.0)
    raise ValueError(f"unknown blend_mode {mode!r}")


def _d_curve(x: np.ndarray) -> np.ndarray:
    """Photoshop's D(x) used by soft-light: square-root for x>0.25 else
    a polynomial that joins smoothly."""
    return np.where(x <= 0.25, ((16.0 * x - 12.0) * x + 4.0) * x, np.sqrt(x))


# ---------------------------------------------------------------------------
# Stroke interpolation
# ---------------------------------------------------------------------------


def stroke_dab_positions(
    p0: tuple[float, float],
    p1: tuple[float, float],
    spacing: float,
) -> list[tuple[float, float]]:
    """Return dab centres along ``p0 → p1`` at ``spacing`` pixels apart.

    Includes ``p1`` so consecutive segments daisy-chain without gaps.
    Excludes ``p0`` so the caller is in charge of stamping the start
    point exactly once at stroke begin.
    """
    if spacing <= 0:
        raise ValueError(f"spacing must be > 0, got {spacing}")
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx = x1 - x0
    dy = y1 - y0
    distance = float(np.hypot(dx, dy))
    if distance <= spacing:
        return [(x1, y1)]
    n_steps = int(np.ceil(distance / spacing))
    out: list[tuple[float, float]] = []
    for i in range(1, n_steps + 1):
        t = i / n_steps
        out.append((x0 + dx * t, y0 + dy * t))
    return out


def spacing_from_brush(size: int, hardness: float) -> float:
    """MediBang-style default spacing — small for soft brushes, larger
    for hard brushes. Stays inside [1, size/2] so we always step at
    least one pixel and never skip half a brush.
    """
    size = max(KERNEL_SIZE_MIN, int(size))
    hardness = max(0.0, min(1.0, float(hardness)))
    fraction = 0.10 + 0.30 * (1.0 - hardness)  # softer brush → finer spacing
    return max(1.0, min(size * 0.5, size * fraction))


# ---------------------------------------------------------------------------
# BrushStroke — state machine fed PointerEvents by a dispatcher
# ---------------------------------------------------------------------------


@dataclass
class BrushStrokeOptions:
    """Per-stroke parameters, frozen at stroke start."""

    color: tuple[int, int, int]
    size: int
    opacity: float
    hardness: float
    blend_mode: str = "normal"
    spacing: float | None = None    # None → spacing_from_brush(size, hardness)


class BrushStroke:
    """Stroke state machine.

    Construction is cheap; call :meth:`begin`, then :meth:`extend` for
    every PointerEvent.move, then :meth:`end` exactly once. Each call
    returns the union damage rect for the canvas repaint.
    """

    def __init__(self, options: BrushStrokeOptions):
        self._options = options
        self._kernel = round_brush_kernel(options.size, options.hardness)
        self._spacing = (
            options.spacing if options.spacing is not None
            else spacing_from_brush(options.size, options.hardness)
        )
        self._last: tuple[float, float] | None = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def begin(self, canvas: np.ndarray, x: float, y: float) -> DabResult:
        if self._active:
            raise RuntimeError("BrushStroke.begin called while already active")
        self._active = True
        self._last = (x, y)
        return apply_dab(
            canvas, x, y, self._kernel, self._options.color,
            opacity=self._options.opacity,
            blend_mode=self._options.blend_mode,
        )

    def extend(self, canvas: np.ndarray, x: float, y: float) -> DabResult:
        if not self._active or self._last is None:
            raise RuntimeError("BrushStroke.extend called before begin()")
        positions = stroke_dab_positions(self._last, (x, y), self._spacing)
        damage = DabResult(0, 0, 0, 0)
        for px, py in positions:
            d = apply_dab(
                canvas, px, py, self._kernel, self._options.color,
                opacity=self._options.opacity,
                blend_mode=self._options.blend_mode,
            )
            damage = _union(damage, d)
        self._last = (x, y)
        return damage

    def end(self, canvas: np.ndarray, x: float, y: float) -> DabResult:
        if not self._active:
            raise RuntimeError("BrushStroke.end called before begin()")
        result = self.extend(canvas, x, y)
        self._active = False
        self._last = None
        return result


def _union(a: DabResult, b: DabResult) -> DabResult:
    if a.is_empty:
        return b
    if b.is_empty:
        return a
    x0 = min(a.x, b.x)
    y0 = min(a.y, b.y)
    x1 = max(a.x + a.w, b.x + b.w)
    y1 = max(a.y + a.h, b.y + b.h)
    return DabResult(x0, y0, x1 - x0, y1 - y0)


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
