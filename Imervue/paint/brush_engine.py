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

from Imervue.paint.blend_modes import BLEND_MODES, blend_rgb

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
    selection: np.ndarray | None = None,
) -> DabResult:
    """Composite ``kernel * color`` into ``canvas`` at ``(cx, cy)`` in-place.

    ``canvas`` must be HxWx4 uint8 RGBA. Returns the damaged rectangle so
    the caller can schedule a localised repaint.

    The "normal" blend mode takes the integer fixed-point fast path
    (:func:`_composite_normal_u8`) which skips the float32 round-trip
    on the RGB channels and the broadcast-copy of the foreground
    colour — the dominant per-dab cost in the previous numpy
    implementation. Other blend modes fall through to the float32
    path with the foreground passed as a 1-D length-3 array so numpy
    broadcasts at the leaf rather than allocating a full HxWx3 copy.
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

    bbox = _dab_bbox(canvas.shape[:2], kernel.shape, cx, cy)
    if bbox is None:
        return DabResult(0, 0, 0, 0)
    cx0, cy0, cx1, cy1, kx0, ky0, kx1, ky1 = bbox

    dst_view = canvas[cy0:cy1, cx0:cx1]
    k = kernel[ky0:ky1, kx0:kx1] * opacity   # alpha for this dab
    if selection is not None:
        if selection.shape != canvas.shape[:2]:
            raise ValueError(
                f"selection mask shape {selection.shape} does not match "
                f"canvas {canvas.shape[:2]}",
            )
        k = k * selection[cy0:cy1, cx0:cx1].astype(np.float32)
    if blend_mode == "normal":
        _composite_normal_u8(dst_view, k, color)
    else:
        _composite_in_place(dst_view, k, color, blend_mode)
    return DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0)


def _dab_bbox(
    canvas_shape: tuple[int, int],
    kernel_shape: tuple[int, int],
    cx: float,
    cy: float,
) -> tuple[int, int, int, int, int, int, int, int] | None:
    """Clip the kernel placement against the canvas bounds.

    Returns ``(cx0, cy0, cx1, cy1, kx0, ky0, kx1, ky1)`` — the canvas
    slice and the matching kernel slice — or ``None`` when the dab is
    fully off-canvas. Pulled out of :func:`apply_dab` so the eraser
    path can share the bookkeeping without duplicating it.
    """
    kh, kw = kernel_shape
    h, w = canvas_shape
    x0 = int(round(cx)) - kw // 2
    y0 = int(round(cy)) - kh // 2
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(w, x0 + kw)
    cy1 = min(h, y0 + kh)
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    return (
        cx0, cy0, cx1, cy1,
        cx0 - x0, cy0 - y0,
        cx0 - x0 + (cx1 - cx0), cy0 - y0 + (cy1 - cy0),
    )


def apply_erase_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    *,
    opacity: float = 1.0,
    selection: np.ndarray | None = None,
) -> DabResult:
    """Subtract ``kernel * opacity`` from ``canvas`` alpha, in-place.

    Eraser semantics — drop alpha by the kernel weight. **Pixels whose
    alpha falls to zero have their RGB channels cleared too**, so a
    later soft-brush stroke that re-touches the erased region doesn't
    pull lingering colour into its anti-aliased edges (which would
    show up as a faint halo of the previously-erased colour, e.g.
    blue ink seeping into a red brush stroke painted over what used
    to be a blue line).

    Pixels whose alpha drops only *partially* (soft eraser, low
    opacity, masked by selection) keep their RGB unchanged — those
    pixels are still partially visible so the existing colour is
    still meaningful. Only the fully-cleared pixels are scrubbed.

    Uses uint8/int32 fixed-point math throughout — no float32
    intermediates. Within ±1 LSB of the float reference and avoids
    the per-dab allocation churn the original implementation paid.
    """
    _check_canvas(canvas)
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return DabResult(0, 0, 0, 0)

    bbox = _dab_bbox(canvas.shape[:2], kernel.shape, cx, cy)
    if bbox is None:
        return DabResult(0, 0, 0, 0)
    cx0, cy0, cx1, cy1, kx0, ky0, kx1, ky1 = bbox

    k = kernel[ky0:ky1, kx0:kx1] * opacity
    if selection is not None:
        if selection.shape != canvas.shape[:2]:
            raise ValueError(
                f"selection mask shape {selection.shape} does not match "
                f"canvas {canvas.shape[:2]}",
            )
        k = k * selection[cy0:cy1, cx0:cx1].astype(np.float32)
    # Quantise alpha to int32 0..256 so a >> 8 acts as integer divide.
    a = np.clip((k * 256.0).astype(np.int32, copy=False), 0, 256)
    a8 = canvas[cy0:cy1, cx0:cx1, 3].astype(np.int32)
    a8 -= (a8 * a) >> 8
    np.clip(a8, 0, 255, out=a8)
    canvas[cy0:cy1, cx0:cx1, 3] = a8.astype(np.uint8)
    # Clear RGB on pixels whose alpha just hit zero. The eraser used
    # to leave RGB intact "so a re-paint with the same colour has no
    # halo", but in practice that lingering RGB contaminates soft-
    # brush edges with the colour that *was* there — a stronger bug
    # than the halo it tried to avoid.
    cleared = a8 == 0
    if cleared.any():
        canvas[cy0:cy1, cx0:cx1][cleared, :3] = 0
    return DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0)


def sample_pixel(canvas: np.ndarray, x: float, y: float) -> tuple[int, int, int] | None:
    """Read ``(R, G, B)`` at ``(x, y)`` from the canvas. Returns ``None``
    if the coordinates fall outside the canvas. Used by the eyedropper
    tool to feed ToolState.foreground.
    """
    _check_canvas(canvas)
    h, w = canvas.shape[:2]
    ix = int(round(x))
    iy = int(round(y))
    if not (0 <= ix < w and 0 <= iy < h):
        return None
    pixel = canvas[iy, ix]
    return (int(pixel[0]), int(pixel[1]), int(pixel[2]))


def _composite_normal_u8(
    dst_view: np.ndarray,
    alpha: np.ndarray,
    color: tuple[int, int, int],
) -> None:
    """In-place 'normal' blend without a float32 round-trip.

    Quantises ``alpha`` (float32 in ``[0, 1]``) to int32 ``0..256`` so
    a single ``>> 8`` acts as an integer divide-by-256, then runs
    ``out = bg + ((fg - bg) * alpha) >> 8`` per channel using int32
    math. ``fg`` stays as a length-3 array — numpy broadcasts it
    against the per-pixel ``bg`` instead of allocating a full HxWx3
    copy. Output is within ±1 LSB of the float reference for every
    input combination tested in :mod:`tests.test_paint_brush_engine`.

    Pixels whose ``dst.alpha`` is already zero contribute nothing
    visible, so we substitute ``fg`` for ``bg`` on those pixels
    before mixing. Without this the alpha-over blend would pull the
    lingering RGB of an "erased" pixel into the soft edges of the
    new stroke — the user-visible bug was a colour halo where the
    new brush touched a previously-erased region.
    """
    a = np.clip((alpha * 256.0).astype(np.int32, copy=False), 0, 256)
    fg_arr = np.array(color, dtype=np.int32)
    bg = dst_view[..., :3].astype(np.int32)
    transparent = dst_view[..., 3] == 0
    if transparent.any():
        bg[transparent] = fg_arr
    delta = fg_arr[None, None, :] - bg
    delta *= a[..., None]
    delta >>= 8
    bg += delta
    np.clip(bg, 0, 255, out=bg)
    dst_view[..., :3] = bg.astype(np.uint8)
    a8 = dst_view[..., 3].astype(np.int32)
    a8 += ((256 - a8) * a) >> 8
    np.clip(a8, 0, 255, out=a8)
    dst_view[..., 3] = a8.astype(np.uint8)


def _composite_in_place(
    dst: np.ndarray,
    alpha: np.ndarray,
    color: tuple[int, int, int],
    blend_mode: str,
) -> None:
    """Apply ``alpha``-weighted blend of ``color`` onto the RGBA ``dst``.

    Generic float32 path used for non-``normal`` blend modes. The
    foreground colour is passed as a length-3 sequence and broadcast
    by numpy against the per-pixel background — this skips the
    HxWx3 copy the previous implementation made via
    ``np.broadcast_to(...).copy()``. Mirrors the
    :func:`_composite_normal_u8` rule for fully-transparent
    destination pixels: their lingering RGB has no meaningful
    contribution, so we substitute ``fg`` to keep the soft-edge
    blend free of stale colour.
    """
    bg = dst[..., :3].astype(np.float32) / 255.0
    fg = np.array(color, dtype=np.float32) / 255.0   # shape (3,)
    transparent = dst[..., 3] == 0
    if transparent.any():
        bg[transparent] = fg
    blended = blend_rgb(bg, fg, blend_mode)

    a = alpha[..., None]
    out_rgb = bg * (1.0 - a) + blended * a
    dst[..., :3] = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    dst_a = dst[..., 3].astype(np.float32) / 255.0
    new_a = dst_a + (1.0 - dst_a) * alpha
    dst[..., 3] = np.clip(new_a * 255.0, 0.0, 255.0).astype(np.uint8)


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
    """full-featured default spacing — small for soft brushes, larger
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
    selection: np.ndarray | None = None   # bool HxW; paint clipped to True
    kind: str = "pen"               # pen / pencil / marker / airbrush / watercolor
    seed: int = 0                   # RNG seed for kind-specific noise
    tip_path: str | None = None     # custom PNG used as kernel; None = round
    # Pixel-art mode — when True, the kernel is forced to a hard
    # ``size x size`` square of 1.0s (no anti-aliased falloff), dab
    # positions snap to integer pixels, and tip / kind shaping is
    # bypassed. Matches raster paint apps's "ドット絵モード" / Aseprite's
    # pixel brush. Tests in test_paint_brush_engine.py exercise the
    # snap + kernel behaviour.
    pixel_art: bool = False
    # Stroke-tapering — ramp opacity over the first / last N dabs so
    # mouse-only strokes get the soft pen-pressure feel naturally.
    # Both default to 0 (no taper) so existing brushes are unchanged.
    # ``taper_start_dabs`` ramps opacity from 0 → 1 over the first N
    # dabs; ``taper_end_dabs`` is honoured by the dispatcher via
    # :class:`Imervue.paint.tapered_stroke.TaperedStroke` because
    # end-tapering needs lookahead the engine itself doesn't have.
    taper_start_dabs: int = 0
    taper_end_dabs: int = 0


def square_brush_kernel(size: int) -> np.ndarray:
    """Return an ``(N, N)`` float32 kernel with every cell at 1.0.

    The pixel-art kernel: hard square edges, no anti-aliased falloff.
    ``size`` is clamped to the documented brush range.
    """
    size = max(KERNEL_SIZE_MIN, min(KERNEL_SIZE_MAX, int(size)))
    return np.ones((size, size), dtype=np.float32)


class BrushStroke:
    """Stroke state machine.

    Construction is cheap; call :meth:`begin`, then :meth:`extend` for
    every PointerEvent.move, then :meth:`end` exactly once. Each call
    returns the union damage rect for the canvas repaint.
    """

    def __init__(self, options: BrushStrokeOptions):
        from Imervue.paint.brush_dynamics import stylise_kernel
        self._options = options
        self._rng = np.random.default_rng(options.seed)
        # Dab counter for start-taper opacity ramp.
        self._dab_index = 0
        # End-taper buffer — when ``taper_end_dabs > 0`` the most
        # recent N dabs are queued here. Each new dab flushes the
        # oldest at full opacity; on stroke end the buffer is
        # replayed with progressively lower opacity so the tail
        # fades out smoothly. Each entry is ``(x, y, kernel)``.
        self._tail_buffer: list[tuple[float, float, np.ndarray]] = []
        base = _resolve_base_kernel(options)
        # Pixel-art mode bypasses the per-kind noise shaping — the
        # kernel is the hard square already and we don't want any
        # variation between dabs.
        if options.pixel_art:
            self._base_kernel = base
            self._kernel = base
            self._restyle_each_dab = False
        # Re-stylise the kernel each dab for kinds that depend on noise
        # (pencil / airbrush) — store the base + a callable instead of
        # caching one shape so the texture varies along the stroke.
        elif options.kind in ("pencil", "airbrush"):
            self._base_kernel = base
            self._kernel = stylise_kernel(base, options.kind, self._rng)
            self._restyle_each_dab = True
        else:
            self._base_kernel = base
            self._kernel = stylise_kernel(base, options.kind, self._rng)
            self._restyle_each_dab = False
        self._spacing = (
            options.spacing if options.spacing is not None
            else spacing_from_brush(options.size, options.hardness)
        )
        self._last: tuple[float, float] | None = None
        self._active = False
        # Union of dab-damage rects since the last begin() — exposed
        # via :attr:`stroke_damage` so the canvas can request a
        # partial texture upload over only the touched region.
        self._stroke_damage: DabResult = DabResult(0, 0, 0, 0)

    @property
    def is_active(self) -> bool:
        return self._active

    def begin(self, canvas: np.ndarray, x: float, y: float) -> DabResult:
        if self._active:
            raise RuntimeError("BrushStroke.begin called while already active")
        self._active = True
        x, y = self._snap_position(x, y)
        self._last = (x, y)
        self._stroke_damage = DabResult(0, 0, 0, 0)
        damage = self._stage_dab(canvas, x, y)
        self._stroke_damage = _union(self._stroke_damage, damage)
        return damage

    def extend(self, canvas: np.ndarray, x: float, y: float) -> DabResult:
        if not self._active or self._last is None:
            raise RuntimeError("BrushStroke.extend called before begin()")
        x, y = self._snap_position(x, y)
        positions = stroke_dab_positions(self._last, (x, y), self._spacing)
        damage = DabResult(0, 0, 0, 0)
        for raw_px, raw_py in positions:
            if self._options.pixel_art:
                dab_px = float(int(round(raw_px)))
                dab_py = float(int(round(raw_py)))
            else:
                dab_px = raw_px
                dab_py = raw_py
            d = self._stage_dab(canvas, dab_px, dab_py)
            damage = _union(damage, d)
        self._last = (x, y)
        self._stroke_damage = _union(self._stroke_damage, damage)
        return damage

    def _stage_dab(
        self, canvas: np.ndarray, x: float, y: float,
    ) -> DabResult:
        """Apply a dab — directly when no end-taper, otherwise via the
        tail buffer that defers the most recent N dabs."""
        kernel = self._next_kernel()
        end_taper = int(self._options.taper_end_dabs)
        if end_taper <= 0:
            damage = self._paint_dab(canvas, x, y, kernel, fade=1.0)
            self._dab_index += 1
            return damage
        # Buffer this dab. If the buffer is full, the oldest one
        # gets painted at full opacity (it's no longer in the tail
        # window) and the new dab takes its slot.
        damage = DabResult(0, 0, 0, 0)
        self._tail_buffer.append((x, y, kernel))
        if len(self._tail_buffer) > end_taper:
            old_x, old_y, old_kernel = self._tail_buffer.pop(0)
            damage = self._paint_dab(
                canvas, old_x, old_y, old_kernel, fade=1.0,
            )
            self._dab_index += 1
        return damage

    def _paint_dab(
        self,
        canvas: np.ndarray,
        x: float, y: float,
        kernel: np.ndarray,
        *,
        fade: float,
    ) -> DabResult:
        return apply_dab(
            canvas, x, y, kernel, self._options.color,
            opacity=self._taper_start_opacity() * float(fade),
            blend_mode=self._options.blend_mode,
            selection=self._options.selection,
        )

    def _taper_start_opacity(self) -> float:
        """Scale the configured opacity by the start-taper ramp."""
        opacity = self._options.opacity
        ramp = int(self._options.taper_start_dabs)
        if ramp <= 0:
            return opacity
        progress = min(1.0, (self._dab_index + 1) / float(ramp))
        return opacity * progress

    def _flush_tail(self, canvas: np.ndarray) -> DabResult:
        """Drain the end-taper buffer with progressively lower opacity."""
        damage = DabResult(0, 0, 0, 0)
        if not self._tail_buffer:
            return damage
        n = len(self._tail_buffer)
        for i, (x, y, kernel) in enumerate(self._tail_buffer):
            # Fade from near-full at the first buffered dab down to
            # near-zero at the last; (n - i) / (n + 1) keeps both
            # endpoints non-trivial so the transition is smooth.
            fade = max(0.0, (n - i) / float(n + 1))
            d = self._paint_dab(canvas, x, y, kernel, fade=fade)
            damage = _union(damage, d)
            self._dab_index += 1
        self._tail_buffer = []
        return damage

    def _snap_position(self, x: float, y: float) -> tuple[float, float]:
        """Snap ``(x, y)`` to integer pixels when pixel-art mode is on."""
        if not self._options.pixel_art:
            return (x, y)
        return (float(int(round(x))), float(int(round(y))))

    @property
    def stroke_damage(self) -> DabResult:
        """Union of every dab damage rect since the last :meth:`begin`."""
        return self._stroke_damage

    def _next_kernel(self) -> np.ndarray:
        """Return the kernel to stamp for the next dab.

        For deterministic kinds (pen / marker / watercolor) the
        stylised kernel is computed once and reused. For grainy kinds
        (pencil / airbrush) we re-stylise on every dab so the noise
        pattern shifts along the stroke — without that, a long line
        would show the same dot pattern repeated.
        """
        from Imervue.paint.brush_dynamics import stylise_kernel
        if self._restyle_each_dab:
            return stylise_kernel(self._base_kernel, self._options.kind, self._rng)
        return self._kernel

    def end(self, canvas: np.ndarray, x: float, y: float) -> DabResult:
        if not self._active:
            raise RuntimeError("BrushStroke.end called before begin()")
        result = self.extend(canvas, x, y)
        # Flush whatever end-taper buffer remains so the final stroke
        # tail fades naturally instead of cutting off at full opacity.
        tail_damage = self._flush_tail(canvas)
        result = _union(result, tail_damage)
        self._stroke_damage = _union(self._stroke_damage, tail_damage)
        self._active = False
        self._last = None
        return result


def _resolve_base_kernel(options: BrushStrokeOptions) -> np.ndarray:
    """Build the per-stroke base kernel — custom tip if set, else round."""
    if options.pixel_art:
        # Pixel-art mode overrides every other kernel choice — hard
        # square with no falloff, regardless of hardness / kind / tip.
        return square_brush_kernel(options.size)
    if options.tip_path:
        try:
            from Imervue.paint.custom_brush import load_brush_tip
            return load_brush_tip(options.tip_path, options.size)
        except (OSError, ValueError):
            # Fall back to the default round kernel; never crash a stroke.
            return round_brush_kernel(options.size, options.hardness)
    return round_brush_kernel(options.size, options.hardness)


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
