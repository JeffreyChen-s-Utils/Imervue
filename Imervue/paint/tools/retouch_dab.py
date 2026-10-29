"""Dab-stroke retouch tools for the paint workspace — blur, dodge / burn, sponge.

The three share one pointer protocol: press fixes the brush kernel, spacing
and selection snapshot and stamps one dab; each move stamps a dab at every
spacing step along the path; release / leave stamps the last segment and ends
the stroke. :class:`_DabStrokeTool` holds that protocol and the per-stroke
damage rect; each tool supplies only ``_dab``. Re-exported from
:mod:`Imervue.paint.tools.retouch`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.brush_engine import round_brush_kernel, spacing_from_brush
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
from Imervue.paint.damage import from_rect, union_rects

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class _DabStrokeTool:
    """Brush pointer protocol around one ``_dab``; reports each event's damage."""

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._kernel = None
        self._spacing = 1.0
        self._last: tuple[float, float] | None = None
        self._selection_snapshot = None
        self._active = False
        self._damage = _EMPTY_DAMAGE

    @property
    def last_damage(self):
        return self._damage

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
        self._damage = _EMPTY_DAMAGE

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        brush = self._state.brush
        self._kernel = round_brush_kernel(brush.size, brush.hardness)
        self._spacing = spacing_from_brush(brush.size, brush.hardness)
        self._selection_snapshot = self._selection_provider()
        self._last = (evt.x, evt.y)
        self._active = True
        rect = self._dab(canvas, evt.x, evt.y)
        self._damage = from_rect(rect)
        return rect[2] > 0 and rect[3] > 0

    def _extend(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.brush_engine import stroke_dab_positions
        if self._last is None or self._kernel is None:
            return False
        union = (0, 0, 0, 0)
        for px, py in stroke_dab_positions(
            self._last, (evt.x, evt.y), self._spacing,
        ):
            union = union_rects(union, self._dab(canvas, px, py))
        self._last = (evt.x, evt.y)
        self._damage = from_rect(union)
        return union[2] > 0 and union[3] > 0

    def _dab(self, canvas: np.ndarray, px: float, py: float):
        """Apply one dab at ``(px, py)`` and return its ``(x, y, w, h)`` damage."""
        raise NotImplementedError


class _BlurTool(_DabStrokeTool):
    """Local Gaussian blur on each dab — same pointer protocol as brush."""

    def _dab(self, canvas: np.ndarray, px: float, py: float):
        from Imervue.paint.blur import blur_dab
        return blur_dab(
            canvas, px, py, self._kernel,
            strength=max(0.05, self._state.brush.opacity),
            selection=self._selection_snapshot,
        )


class _DodgeBurnTool(_DabStrokeTool):
    """Lighten (dodge) or darken (burn) each dab — brush pointer protocol.

    One class backs both toolbar entries; ``mode`` fixes the sign so the
    dodge instance always lightens and the burn instance always darkens.
    Strength comes from the shared brush-opacity slider and the targeted
    tonal band defaults to midtones.
    """

    def __init__(
        self,
        state: ToolState,
        mode: str,
        selection_provider=None,
        *,
        range_mode: str = "midtones",
    ):
        super().__init__(state, selection_provider)
        self._sign = 1.0 if mode == "dodge" else -1.0
        self._range_mode = range_mode

    def _dab(self, canvas: np.ndarray, px: float, py: float):
        from Imervue.paint.dodge_burn import dodge_burn_dab
        brush = self._state.brush
        amount = self._sign * max(0.05, brush.opacity)
        return dodge_burn_dab(
            canvas, px, py, self._kernel,
            amount=amount, range_mode=self._range_mode,
            selection=self._selection_snapshot,
        )


class _SpongeTool(_DabStrokeTool):
    """Locally saturate or desaturate each dab — brush pointer protocol.

    Defaults to desaturate (the iconic sponge action); ``mode='saturate'``
    flips the sign. Strength comes from the shared brush-opacity slider.
    """

    def __init__(
        self,
        state: ToolState,
        selection_provider=None,
        *,
        mode: str = "desaturate",
    ):
        super().__init__(state, selection_provider)
        self._sign = 1.0 if mode == "saturate" else -1.0

    def _dab(self, canvas: np.ndarray, px: float, py: float):
        from Imervue.paint.sponge import sponge_dab
        brush = self._state.brush
        amount = self._sign * max(0.05, brush.opacity)
        return sponge_dab(
            canvas, px, py, self._kernel,
            amount=amount, selection=self._selection_snapshot,
        )
