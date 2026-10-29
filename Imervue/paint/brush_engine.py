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

The kernels and dab spacing live in :mod:`Imervue.paint.brush_kernels` and
the dab compositing in :mod:`Imervue.paint.brush_dab`; this module re-exports
both, so it stays the one import location for callers.

The module is Qt-free so the rasterisation can be unit-tested without
a display server. The Paint workspace's tool dispatcher feeds it
PointerEvents and reads back a damaged-rect that the canvas can use to
schedule a partial repaint.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from Imervue.paint.blend_modes import BLEND_MODES, blend_rgb
from Imervue.paint.brush_dab import (
    DabResult,
    _check_canvas,
    _composite_in_place,
    _composite_normal_u8,
    _union,
    apply_dab,
    apply_erase_dab,
    dab_bbox,
    sample_pixel,
)
from Imervue.paint.brush_kernels import (
    KERNEL_SIZE_MAX,
    KERNEL_SIZE_MIN,
    _resolve_base_kernel,
    round_brush_kernel,
    spacing_from_brush,
    square_brush_kernel,
    stroke_dab_positions,
)

__all__ = [
    "BLEND_MODES",
    "KERNEL_SIZE_MAX",
    "KERNEL_SIZE_MIN",
    "BrushStroke",
    "BrushStrokeOptions",
    "DabResult",
    "_check_canvas",
    "_composite_in_place",
    "_composite_normal_u8",
    "_resolve_base_kernel",
    "_union",
    "apply_dab",
    "apply_erase_dab",
    "blend_rgb",
    "dab_bbox",
    "round_brush_kernel",
    "sample_pixel",
    "spacing_from_brush",
    "square_brush_kernel",
    "stroke_dab_positions",
]


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
    # bypassed. Matches raster paint apps' "ドット絵モード" / Aseprite's
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
    # Per-dab randomisation (``Imervue.paint.brush_random``): ``scatter``
    # moves each dab up to that fraction of ``size`` off the stroke,
    # ``color_jitter`` shifts each dab's colour in HSV, and ``follow_tilt``
    # shapes the kernel by the pen tilt given to :meth:`BrushStroke.set_tilt`.
    # Pixel-art strokes keep their hard square kernel and ignore the tilt.
    scatter: float = 0.0
    color_jitter: float = 0.0
    follow_tilt: bool = False


#: One dab of a stroke: ``(x, y, kernel, rgb)``.
_Dab = tuple[float, float, np.ndarray, tuple[int, int, int]]


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
        # fades out smoothly. Each entry is ``(x, y, kernel, color)``.
        self._tail_buffer: list[_Dab] = []
        # Pen tilt for ``follow_tilt`` and the kernel shaped for it, kept
        # until the tilt changes (shaping resamples the whole kernel).
        self._tilt = (0.0, 0.0)
        self._tilted: tuple[tuple[float, float], np.ndarray, np.ndarray] | None = None
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

    def set_tilt(self, tilt_x: float, tilt_y: float) -> None:
        """Set the pen tilt (each axis in ``[-1, 1]``) that ``follow_tilt`` dabs follow."""
        self._tilt = (float(tilt_x), float(tilt_y))

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
        dab = self._next_dab(x, y)
        end_taper = int(self._options.taper_end_dabs)
        if end_taper <= 0:
            damage = self._paint_dab(canvas, dab, fade=1.0)
            self._dab_index += 1
            return damage
        # Buffer this dab. If the buffer is full, the oldest one
        # gets painted at full opacity (it's no longer in the tail
        # window) and the new dab takes its slot.
        damage = DabResult(0, 0, 0, 0)
        self._tail_buffer.append(dab)
        if len(self._tail_buffer) > end_taper:
            damage = self._paint_dab(canvas, self._tail_buffer.pop(0), fade=1.0)
            self._dab_index += 1
        return damage

    def _next_dab(self, x: float, y: float) -> _Dab:
        """Position, kernel and colour of the next dab, randomised as the options ask."""
        from Imervue.paint.brush_random import jitter_color, scatter_offset
        options = self._options
        kernel = self._next_kernel()
        if options.scatter > 0:
            dx, dy = scatter_offset(options.size, options.scatter, self._rng)
            x, y = self._snap_position(x + dx, y + dy)
        color = jitter_color(options.color, options.color_jitter, self._rng)
        return (x, y, kernel, color)

    def _paint_dab(self, canvas: np.ndarray, dab: _Dab, *, fade: float) -> DabResult:
        x, y, kernel, color = dab
        return apply_dab(
            canvas, x, y, kernel, color,
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
        for i, dab in enumerate(self._tail_buffer):
            # Fade from near-full at the first buffered dab down to
            # near-zero at the last; (n - i) / (n + 1) keeps both
            # endpoints non-trivial so the transition is smooth.
            fade = max(0.0, (n - i) / float(n + 1))
            d = self._paint_dab(canvas, dab, fade=fade)
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
            kernel = stylise_kernel(self._base_kernel, self._options.kind, self._rng)
        else:
            kernel = self._kernel
        if not self._options.follow_tilt or self._options.pixel_art:
            return kernel
        return self._tilted_kernel(kernel)

    def _tilted_kernel(self, kernel: np.ndarray) -> np.ndarray:
        """*kernel* shaped by the current pen tilt, reusing the last result while both hold."""
        from Imervue.paint.brush_random import tilt_kernel
        cached = self._tilted
        if cached is not None and cached[0] == self._tilt and cached[1] is kernel:
            return cached[2]
        shaped = tilt_kernel(kernel, *self._tilt)
        self._tilted = (self._tilt, kernel, shaped)
        return shaped

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

    def dispose(self) -> None:
        """Release any resources the stroke holds when abandoned mid-way.

        A CPU stroke draws straight onto the layer buffer and owns nothing to
        free, so the base is a no-op. GPU strokes override this to free their
        framebuffer/textures when a tool switch cancels a stroke before ``end``.
        """
