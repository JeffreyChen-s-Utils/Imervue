"""The pointer snapshot the paint canvas hands to its tool dispatcher.

Kept apart from the Qt canvas so tools and tests can build events without
importing the OpenGL widget. ``Imervue.paint.canvas`` re-exports both names.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class PointerEvent:
    """Snapshot passed to a tool dispatcher.

    Image-space coordinates may fall outside the canvas bounds when the
    user drags off the edge. Tools can clamp / discard at their
    discretion.
    """

    phase: str            # "press" | "move" | "release" | "leave"
    x: float              # image-space pixel x (float for sub-pixel strokes)
    y: float              # image-space pixel y
    button: int           # Qt.MouseButton value, 0 if no button
    modifiers: int        # Qt.KeyboardModifier flags
    pressure: float       # 0.0..1.0 — 1.0 if no tablet
    # Pen tilt — projection of the stylus onto the canvas plane.
    # 0.0 == perpendicular (no tilt). Mice / fingers always emit 0.0.
    tilt_x: float = 0.0   # -1.0..1.0 — left/right tilt
    tilt_y: float = 0.0   # -1.0..1.0 — up/down tilt


# A tool dispatcher receives one PointerEvent at a time. Returning ``True``
# tells the canvas to schedule a repaint (so brush previews are visible).
ToolDispatcher = Callable[[PointerEvent], bool]
