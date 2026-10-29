"""Validate whole-ruler replacements and keyword ruler updates."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from Imervue.paint.rulers import Ruler
from Imervue.paint.tool_state_settings import EVENT_RULER, validate_choice


class RulerStateMixin:
    """Validate whole-ruler replacements and keyword ruler updates."""

    def set_ruler(self, ruler: Ruler | None = None, **kwargs: Any) -> bool:
        """Replace the active ruler.

        Pass either a fully-built :class:`Ruler` (``set_ruler(ruler)``) or
        keyword overrides to mutate one field at a time
        (``set_ruler(mode="linear", angle_deg=45)``); kwargs build a new
        Ruler from the current ruler with only the named fields replaced.
        Unknown modes raise ``ValueError`` so a typo can't silently fall
        back to off.
        """
        from Imervue.paint.rulers import RULER_MODES
        if ruler is None:
            ruler = replace(self.ruler, **kwargs) if kwargs else self.ruler
        elif kwargs:
            raise ValueError("set_ruler accepts either ruler= or **kwargs, not both")
        validate_choice(ruler.mode, RULER_MODES, "ruler mode")
        return self._change("ruler", ruler, EVENT_RULER)
