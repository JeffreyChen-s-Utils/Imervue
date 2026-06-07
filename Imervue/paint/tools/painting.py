"""Brush, eraser, fill and eyedropper tools.

Extracted from ``tool_dispatcher``; re-exported there for compatibility.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.brush_engine import (
    BrushStroke,
    BrushStrokeOptions,
    apply_erase_dab,
    round_brush_kernel,
    sample_pixel,
    spacing_from_brush,
)
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
from Imervue.paint.fill import flood_fill

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class BrushTool:
    """Standard brush — paints colour through the current brush kernel.

    The pipeline applied to every cursor sample is **ruler-snap →
    stabiliser → symmetry mirror**. Each stage is opt-in: an off-mode
    ruler is identity, a zero-strength stabiliser is bypassed, and an
    off-mode symmetry mirror produces a single stroke. With everything
    on, the user gets a snapped, smoothed, mirrored stroke from one
    cursor input.

    Ruler / symmetry geometry is snapshotted at press time so a
    mid-stroke mode change or canvas resize can't tear the active
    stroke.
    """

    def __init__(
        self, state: ToolState,
        selection_provider=None,
        panel_clip_provider=None,
    ):
        from Imervue.paint.rulers import Ruler
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        # ``panel_clip_provider(x, y)`` returns a bool HxW mask True
        # only inside the panel containing ``(x, y)``, or None when
        # there is no panel layout / the press point is in a gutter.
        # The snap-to-panel option ANDs this with the live selection
        # at press time so a stroke that crosses a gutter doesn't
        # paint outside its panel.
        self._panel_clip_provider = panel_clip_provider or (lambda _x, _y: None)
        self._strokes: list[BrushStroke] = []
        self._stabilizer = None   # type: ignore[assignment]
        self._mode: str = "off"
        self._origin: tuple[float, float] = (0.0, 0.0)
        self._ruler: Ruler = Ruler()
        # Press-point of the active stroke — fed to the perspective
        # ruler so its snap line passes through where the user pressed.
        self._stroke_anchor: tuple[float, float] | None = None
        self.last_damage = _EMPTY_DAMAGE

    def _panel_clipped_selection(
        self, sx: float, sy: float,
    ) -> np.ndarray | None:
        """Return the live selection ANDed with the panel mask if applicable.

        Off when ``state.snap_to_panel`` is False or the panel
        provider returns None for the press point.
        """
        selection = self._selection_provider()
        if not self._state.snap_to_panel:
            return selection
        panel_mask = self._panel_clip_provider(sx, sy)
        if panel_mask is None:
            return selection
        if selection is None:
            return panel_mask
        return selection & panel_mask

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self.last_damage = _EMPTY_DAMAGE
            handled = self._begin(evt, canvas)
            if handled:
                self.last_damage = self._collect_damage()
            return handled
        if evt.phase == "move" and self._strokes:
            x, y = self._snap(evt.x, evt.y)
            x, y = self._smoothed_xy(x, y)
            self._extend_all(canvas, x, y)
            self.last_damage = self._collect_damage()
            return True
        if evt.phase in ("release", "leave") and self._strokes:
            # Leaving the canvas is treated like a release so the state
            # machine never strands an active stroke.
            sx, sy = self._snap(evt.x, evt.y)
            self._drain_to(canvas, sx, sy)
            self._end_all(canvas, sx, sy)
            self.last_damage = self._collect_damage()
            self._strokes = []
            self._stabilizer = None
            self._stroke_anchor = None
            return True
        return False

    def _collect_damage(self):
        from Imervue.paint.damage import from_dab_result
        damage = _EMPTY_DAMAGE
        for stroke in self._strokes:
            damage = damage.union(from_dab_result(stroke.stroke_damage))
        return damage

    def cancel(self) -> None:
        self._strokes = []
        self._stabilizer = None
        self._stroke_anchor = None

    def _smoothed_xy(self, x: float, y: float) -> tuple[float, float]:
        if self._stabilizer is None:
            return (x, y)
        sx, sy = self._stabilizer.step(x, y)
        # Re-snap after the stabiliser so curved-ruler interpolation is
        # pulled back onto the track. Idempotent for points already on.
        return self._snap(sx, sy)

    def _drain_to(self, canvas: np.ndarray, x: float, y: float) -> None:
        if self._stabilizer is None or not self._strokes:
            return
        for px, py in self._stabilizer.flush(x, y):
            rx, ry = self._snap(px, py)
            self._extend_all(canvas, rx, ry)

    def _snap(self, x: float, y: float) -> tuple[float, float]:
        from Imervue.paint.rulers import snap_to_ruler
        sx, sy = snap_to_ruler(
            (x, y), self._ruler, stroke_anchor=self._stroke_anchor,
        )
        if self._state.snap_to_pixel:
            from Imervue.paint.visual_guides import snap_to_pixel
            sx, sy = snap_to_pixel(sx, sy)
        return (sx, sy)

    def _mirror(self, x: float, y: float) -> list[tuple[float, float]]:
        from Imervue.paint.symmetry import mirror_points
        return mirror_points((x, y), self._mode, self._origin)

    def _extend_all(self, canvas: np.ndarray, x: float, y: float) -> None:
        for stroke, (px, py) in zip(self._strokes, self._mirror(x, y), strict=True):
            stroke.extend(canvas, px, py)

    def _end_all(self, canvas: np.ndarray, x: float, y: float) -> None:
        for stroke, (px, py) in zip(self._strokes, self._mirror(x, y), strict=True):
            stroke.end(canvas, px, py)

    # ---- internals -------------------------------------------------------

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.brush_dynamics import (
            pressure_opacity_factor,
            pressure_size_factor,
        )
        from Imervue.paint.stabilizer import StrokeStabilizer
        import time
        # No foreground colour → brush is in the "transparent / no
        # colour" state set from the colour dock. Painting with no
        # colour is a no-op rather than an error so the user can
        # leave the slot transparent without having to flip back to
        # a different tool to stop deposition.
        if self._state.foreground is None:
            return False
        brush = self._state.brush
        # Stroke begins → user has committed to this colour. Record
        # it in recents now so subsequent slider tweaks don't re-bump
        # the same colour to the front.
        self._state.record_foreground_in_history()
        # Snapshot the ruler at press time, record the stroke anchor
        # for the perspective ruler, then snap the press point so
        # downstream stabiliser + mirror stages see a point on the track.
        self._ruler = self._state.ruler
        self._stroke_anchor = (float(evt.x), float(evt.y))
        sx, sy = self._snap(evt.x, evt.y)
        # Stabiliser smooths jittery input. strength=0 short-circuits the
        # filter so cheap mice with no jitter pay zero cost.
        if brush.stabilizer > 0.0:
            self._stabilizer = StrokeStabilizer(brush.stabilizer)
            self._stabilizer.begin(sx, sy)
        else:
            self._stabilizer = None
        # Pen pressure scales BOTH size and opacity — raster paint apps uses both
        # axes so a pen line tapers in width as well as ink density.
        size_scaled = max(1, int(round(brush.size * pressure_size_factor(evt.pressure))))
        opacity_scaled = brush.opacity * pressure_opacity_factor(evt.pressure)
        # Snapshot symmetry mode + origin at stroke start so a mid-stroke
        # mode change or canvas resize doesn't tear the mirror geometry.
        self._mode = self._state.symmetry_mode
        h, w = canvas.shape[:2]
        self._origin = (w / 2.0, h / 2.0)
        options = BrushStrokeOptions(
            color=self._state.foreground,
            size=size_scaled,
            opacity=opacity_scaled,
            hardness=brush.hardness,
            blend_mode=brush.blend_mode,
            selection=self._panel_clipped_selection(sx, sy),
            kind=brush.kind,
            seed=int(time.monotonic_ns() & 0xFFFFFFFF),
            tip_path=brush.tip_path,
            pixel_art=self._state.snap_to_pixel,
        )
        from Imervue.paint.gpu_brush import make_brush_stroke
        # GPU stroke uses a per-stroke FBO that can't see sibling
        # strokes' updates without an expensive per-extend re-upload —
        # so the symmetry path stays on the CPU brush. Single
        # (un-mirrored) strokes go through the factory which picks
        # GPU when GL is current and the options qualify.
        mirror_positions = list(self._mirror(sx, sy))
        prefer_gpu = len(mirror_positions) == 1
        self._strokes = []
        for px, py in mirror_positions:
            stroke = make_brush_stroke(options, prefer_gpu=prefer_gpu)
            stroke.begin(canvas, px, py)
            self._strokes.append(stroke)
        return True


# ---------------------------------------------------------------------------
# Eraser tool
# ---------------------------------------------------------------------------


class EraserTool:
    """Eraser — knocks alpha down through the current brush kernel.

    Re-implements the brush stroke loop because the rasteriser is
    designed for additive paint; the eraser path is short enough that
    re-using BrushStroke would obscure rather than help.
    """

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._kernel = None
        self._spacing = 1.0
        self._opacity = 1.0
        self._selection_snapshot: np.ndarray | None = None
        self._last: tuple[float, float] | None = None
        self._active = False

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            return self._begin(evt, canvas)
        if evt.phase == "move" and self._active:
            return self._extend(evt, canvas)
        if evt.phase in ("release", "leave") and self._active:
            self._extend(evt, canvas)
            self._active = False
            self._last = None
            return True
        return False

    def cancel(self) -> None:
        self._active = False
        self._last = None

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        brush = self._state.brush
        self._kernel = round_brush_kernel(brush.size, brush.hardness)
        self._spacing = spacing_from_brush(brush.size, brush.hardness)
        pressure = max(0.1, min(1.0, evt.pressure))
        self._opacity = brush.opacity * pressure
        self._selection_snapshot = self._selection_provider()
        self._last = (evt.x, evt.y)
        self._active = True
        apply_erase_dab(
            canvas, evt.x, evt.y, self._kernel,
            opacity=self._opacity, selection=self._selection_snapshot,
        )
        return True

    def _extend(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if self._last is None or self._kernel is None:
            return False
        from Imervue.paint.brush_engine import stroke_dab_positions
        for px, py in stroke_dab_positions(self._last, (evt.x, evt.y), self._spacing):
            apply_erase_dab(
                canvas, px, py, self._kernel,
                opacity=self._opacity, selection=self._selection_snapshot,
            )
        self._last = (evt.x, evt.y)
        return True


# ---------------------------------------------------------------------------
# Eyedropper
# ---------------------------------------------------------------------------


class FillTool:
    """Paint bucket — single-click flood fills the region under the cursor.

    ``selection_provider`` returns the active selection mask (or
    ``None``) at click time. ``reference_provider`` is optional and
    returns the HxWx4 RGBA buffer of the document's reference layer
    when raster paint apps's "Reference Layer" mode is on; ``None`` falls the
    fill back to sampling its own target.
    """

    def __init__(
        self,
        state: ToolState,
        selection_provider=None,
        reference_provider=None,
    ):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._reference_provider = reference_provider or (lambda: None)

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase != "press":
            return False
        # No foreground colour to deposit — fill is a no-op so the
        # user can leave the slot transparent without surprises.
        if self._state.foreground is None:
            return False
        fill = self._state.fill
        reference = (
            self._reference_provider() if fill.use_reference_layer else None
        )
        result = flood_fill(
            canvas,
            seed_x=int(round(evt.x)),
            seed_y=int(round(evt.y)),
            color=self._state.foreground,
            tolerance=fill.tolerance,
            contiguous=fill.contiguous,
            selection=self._selection_provider(),
            reference_image=reference,
            expand=fill.expand_px,
            gap_close=fill.gap_close_px,
        )
        return not result.is_empty


class EyedropperTool:
    """Click-to-pick: writes the canvas pixel under the cursor to FG.

    Move events while the button is held also update the colour so the
    user can scrub across the canvas to find the right shade — a
    raster paint apps convention. Modifier-aware: holding Alt picks BG instead.

    ``composite_provider`` returns the document's flattened RGBA buffer
    when raster paint apps's "Sample All Layers" mode is on. ``None`` falls
    the sample back to the active layer only — the legacy default.
    """

    ALT_MOD_VALUE: int

    def __init__(
        self,
        state: ToolState,
        composite_provider=None,
    ):
        self._state = state
        # Cache the alt modifier value at construction time; importing Qt
        # in this module keeps the dispatcher Qt-free at import.
        from PySide6.QtCore import Qt
        self.ALT_MOD_VALUE = int(Qt.KeyboardModifier.AltModifier.value)
        self._active = False
        self._composite_provider = composite_provider or (lambda: None)

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        # The eyedropper updates ToolState.foreground_color but never
        # mutates the canvas, so it always reports ``False`` per the
        # dispatcher contract (True == "I changed pixels"). Sonar
        # flags this as S3516 ("always returns the same value") but
        # the bool return type is non-negotiable — every tool's
        # ``handle`` must return a bool so the dispatcher knows when
        # to invalidate the composite.
        if evt.phase == "press":
            self._active = True
            self._sample(evt, canvas)
        elif evt.phase == "move" and self._active:
            self._sample(evt, canvas)
        elif evt.phase in ("release", "leave"):
            self._active = False
        return False

    def cancel(self) -> None:
        self._active = False

    def _sample(self, evt: PointerEvent, canvas: np.ndarray) -> None:
        source = canvas
        if self._state.eyedropper_sample_all_layers:
            composite = self._composite_provider()
            if composite is not None:
                source = composite
        pixel = sample_pixel(source, evt.x, evt.y)
        if pixel is None:
            return
        if evt.modifiers & self.ALT_MOD_VALUE:
            self._state.set_background(pixel)
        else:
            # Eyedropper is a deliberate "I want this colour" action,
            # so commit it to the recents history.
            self._state.set_foreground(pixel, commit=True)

