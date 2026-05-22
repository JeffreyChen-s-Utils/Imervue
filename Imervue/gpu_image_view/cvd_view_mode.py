"""View-time colour-vision-deficiency (CVD) simulation for the image
viewer.

The full algorithm lives in :mod:`Imervue.paint.color_blindness` —
this module wraps it as a *view mode*: a module-level toggle that
:func:`Imervue.gpu_image_view.images.image_loader.load_image_file`
consults after the recipe pipeline so the displayed image carries
the simulation without touching the source file or the user's
recipe.

Pure design — no Qt, no state on disk. The viewer reloads the
current image when the user changes mode so the toggle stays
instant from the user's POV without rewriting the GL pipeline to
do shader-level CVD.

Modes:

* ``None``           — bypass; the loader returns the image unmodified.
* ``"protanopia"``   — red-blind simulation.
* ``"deuteranopia"`` — green-blind (most common red-green CVD).
* ``"tritanopia"``   — blue-blind simulation.
* ``"achromatopsia"`` — full greyscale.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from Imervue.paint.color_blindness import SIMULATION_KINDS, simulate

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("Imervue.gpu_image_view.cvd_view_mode")

VALID_MODES: tuple[str, ...] = SIMULATION_KINDS
"""The set of CVD kinds accepted by :func:`set_view_mode`. Re-exported
from the paint module so callers don't have to import both."""

_state: dict[str, object] = {"mode": None, "severity": 1.0}


def view_mode() -> str | None:
    """Currently-active CVD mode, or ``None`` when simulation is off."""
    mode = _state.get("mode")
    return mode if isinstance(mode, str) else None


def view_severity() -> float:
    """Blend between identity (0.0) and full simulation (1.0)."""
    severity = _state.get("severity", 1.0)
    try:
        return max(0.0, min(1.0, float(severity)))
    except (TypeError, ValueError):
        return 1.0


def set_view_mode(mode: str | None, *, severity: float = 1.0) -> None:
    """Toggle / change the active CVD mode.

    ``None`` turns simulation off; any string in :data:`VALID_MODES`
    enables that simulation. Anything else is silently coerced to
    ``None`` so a typo'd menu entry can't crash the load path.
    """
    if mode is None or mode not in VALID_MODES:
        if mode is not None:
            logger.warning("ignoring unknown CVD mode %r", mode)
        _state["mode"] = None
        return
    _state["mode"] = mode
    try:
        _state["severity"] = max(0.0, min(1.0, float(severity)))
    except (TypeError, ValueError):
        _state["severity"] = 1.0


def is_active() -> bool:
    """``True`` when :func:`apply_if_active` would actually do work.
    Lets callers skip the function-call overhead on the hot path."""
    return view_mode() is not None and view_severity() > 0.0


def apply_if_active(image: np.ndarray) -> np.ndarray:
    """Run :func:`simulate` on ``image`` when a mode is active, return
    the original buffer otherwise.

    Tolerant of a wrong-shaped input: simulate raises ``ValueError``
    for non-HxWx4 uint8 arrays, but the loader pipeline guarantees
    that shape before reaching us. Still defensively log + bypass
    rather than crash if a future caller forgets.
    """
    if not is_active():
        return image
    try:
        return simulate(image, view_mode(), severity=view_severity())
    except ValueError as exc:
        logger.warning("CVD simulate failed (%s); bypassing", exc)
        return image
