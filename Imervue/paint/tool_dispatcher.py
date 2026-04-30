"""Tool dispatcher — routes PointerEvents to the active tool handler.

Strategy pattern. A :class:`ToolDispatcher` holds one handler instance
per tool, looks up the active tool from the shared
:class:`Imervue.paint.tool_state.ToolState` for every event, and lets
that handler mutate the canvas in place. Returning ``True`` from the
dispatcher tells :class:`Imervue.paint.canvas.PaintCanvas` to re-upload
the texture on the next paint, so canvases never repaint unnecessarily.

Each tool handler implements:

* :meth:`Tool.handle(evt, canvas) -> bool` — receive one
  :class:`PointerEvent`, mutate ``canvas`` (a numpy array) in place,
  return ``True`` if anything visible changed.

Phase 2b ships brush, eraser and eyedropper. Phase 2c-2e fill in the
remaining tools by registering more handlers in
:meth:`ToolDispatcher._build_handlers`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

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
from Imervue.paint.fill import flood_fill

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

logger = logging.getLogger("Imervue.paint.dispatcher")


# ---------------------------------------------------------------------------
# Tool protocol — every tool must implement this.
# ---------------------------------------------------------------------------


class Tool(Protocol):
    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        """Process one event. Returns ``True`` if the canvas changed."""


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class ToolDispatcher:
    """Callable that routes events to the active tool handler.

    Wire it into the canvas via
    ``canvas.set_tool_dispatcher(dispatcher)``. The dispatcher reads
    :attr:`ToolState.tool` on each event so a mid-stroke tool switch
    cleanly cancels the previous handler's stroke (it never sees the
    next event, so its state is implicitly dropped).
    """

    def __init__(self, state: ToolState, image_provider):
        """``image_provider`` is a callable returning the live numpy
        canvas (or ``None`` if no image is loaded). Decoupled from the
        Qt canvas so tests can pass a static array."""
        self._state = state
        self._image_provider = image_provider
        self._handlers: dict[str, Tool] = self._build_handlers()
        self._active_tool: str | None = None

    def __call__(self, evt: PointerEvent) -> bool:
        canvas = self._image_provider()
        if canvas is None:
            return False
        tool_name = self._state.tool
        if tool_name != self._active_tool and self._active_tool in self._handlers:
            # User flipped tools mid-stroke — give the old handler a
            # chance to clean up internal state if it cares.
            cancel = getattr(self._handlers[self._active_tool], "cancel", None)
            if callable(cancel):
                cancel()
        self._active_tool = tool_name
        handler = self._handlers.get(tool_name)
        if handler is None:
            return False
        try:
            return handler.handle(evt, canvas)
        except (ValueError, RuntimeError) as exc:
            logger.warning("tool %r raised: %s", tool_name, exc)
            return False

    # ---- internals -------------------------------------------------------

    def _build_handlers(self) -> dict[str, Tool]:
        return {
            "brush": BrushTool(self._state),
            "eraser": EraserTool(self._state),
            "eyedropper": EyedropperTool(self._state),
            "fill": FillTool(self._state),
        }


# ---------------------------------------------------------------------------
# Brush tool
# ---------------------------------------------------------------------------


class BrushTool:
    """Standard brush — paints colour through the current brush kernel."""

    def __init__(self, state: ToolState):
        self._state = state
        self._stroke: BrushStroke | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            return self._begin(evt, canvas)
        if evt.phase == "move" and self._stroke is not None:
            self._stroke.extend(canvas, evt.x, evt.y)
            return True
        if evt.phase == "release" and self._stroke is not None:
            self._stroke.end(canvas, evt.x, evt.y)
            self._stroke = None
            return True
        if evt.phase == "leave" and self._stroke is not None:
            # Treat leaving the canvas as a stroke end so we don't strand
            # the state machine in an active stroke.
            self._stroke.end(canvas, evt.x, evt.y)
            self._stroke = None
            return True
        return False

    def cancel(self) -> None:
        self._stroke = None

    # ---- internals -------------------------------------------------------

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        brush = self._state.brush
        # Pen pressure scales the dab opacity (with a floor so light
        # pressure still puts paint down).
        pressure = max(0.1, min(1.0, evt.pressure))
        opacity = brush.opacity * pressure
        options = BrushStrokeOptions(
            color=self._state.foreground,
            size=brush.size,
            opacity=opacity,
            hardness=brush.hardness,
            blend_mode=brush.blend_mode,
        )
        self._stroke = BrushStroke(options)
        self._stroke.begin(canvas, evt.x, evt.y)
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

    def __init__(self, state: ToolState):
        self._state = state
        self._kernel = None
        self._spacing = 1.0
        self._opacity = 1.0
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
        self._last = (evt.x, evt.y)
        self._active = True
        apply_erase_dab(canvas, evt.x, evt.y, self._kernel, opacity=self._opacity)
        return True

    def _extend(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if self._last is None or self._kernel is None:
            return False
        from Imervue.paint.brush_engine import stroke_dab_positions
        for px, py in stroke_dab_positions(self._last, (evt.x, evt.y), self._spacing):
            apply_erase_dab(canvas, px, py, self._kernel, opacity=self._opacity)
        self._last = (evt.x, evt.y)
        return True


# ---------------------------------------------------------------------------
# Eyedropper
# ---------------------------------------------------------------------------


class FillTool:
    """Paint bucket — single-click flood fills the region under the cursor."""

    def __init__(self, state: ToolState):
        self._state = state

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase != "press":
            return False
        result = flood_fill(
            canvas,
            seed_x=int(round(evt.x)),
            seed_y=int(round(evt.y)),
            color=self._state.foreground,
            tolerance=self._state.fill.tolerance,
            contiguous=self._state.fill.contiguous,
        )
        return not result.is_empty


class EyedropperTool:
    """Click-to-pick: writes the canvas pixel under the cursor to FG.

    Move events while the button is held also update the colour so the
    user can scrub across the canvas to find the right shade — a
    MediBang convention. Modifier-aware: holding Alt picks BG instead.
    """

    ALT_MOD_VALUE: int

    def __init__(self, state: ToolState):
        self._state = state
        # Cache the alt modifier value at construction time; importing Qt
        # in this module keeps the dispatcher Qt-free at import.
        from PySide6.QtCore import Qt
        self.ALT_MOD_VALUE = int(Qt.KeyboardModifier.AltModifier.value)
        self._active = False

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._active = True
            self._sample(evt, canvas)
            return False  # canvas unchanged — only state changed
        if evt.phase == "move" and self._active:
            self._sample(evt, canvas)
            return False
        if evt.phase in ("release", "leave"):
            self._active = False
            return False
        return False

    def cancel(self) -> None:
        self._active = False

    def _sample(self, evt: PointerEvent, canvas: np.ndarray) -> None:
        pixel = sample_pixel(canvas, evt.x, evt.y)
        if pixel is None:
            return
        if evt.modifiers & self.ALT_MOD_VALUE:
            self._state.set_background(pixel)
        else:
            self._state.set_foreground(pixel)
