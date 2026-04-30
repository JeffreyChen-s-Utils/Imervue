"""Pixel grid + visual guide overlays.

Two flavours of overlay the canvas widget can blit on top of the
layer composite:

* :class:`Guide` — single horizontal / vertical line at a fixed
  pixel position. Drawn fully across the canvas. Stored on the
  document so the same guide line shows up across reopen.
* :class:`GridSpec` — regular minor + major grid intervals. The
  minor lines tile every ``minor_interval`` pixels; major lines
  appear every ``major_every`` minor lines (typical setup: minor =
  10, major every 5 = highlighted line every 50 px).

:func:`render_overlay` paints both layers into a fresh HxWx4 RGBA
buffer the canvas can alpha-blit. Pure-numpy / Qt-free; the dock
widget only needs to upload the result as a texture.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

GUIDE_ORIENTATIONS = ("horizontal", "vertical")
DEFAULT_GUIDE_COLOR = (0, 200, 255, 200)
DEFAULT_GRID_MINOR_COLOR = (128, 128, 128, 64)
DEFAULT_GRID_MAJOR_COLOR = (128, 128, 128, 160)
MIN_GRID_INTERVAL = 2
MAX_GRID_INTERVAL = 4096

# Minimum on-screen size of a single image pixel (in widget pixels)
# at which the pixel grid is visually useful — below this the grid
# lines themselves crowd out the underlying art and the user gets
# moire instead of guidance. 8.0 ≈ 800 % zoom for a 1:1 widget.
PIXEL_GRID_MIN_ZOOM = 8.0


def should_show_pixel_grid(zoom: float) -> bool:
    """Whether to draw the per-pixel grid at the given canvas zoom.

    Returns ``True`` when the user has zoomed past
    :data:`PIXEL_GRID_MIN_ZOOM` so the canvas widget can decide
    whether to spend the per-paint cost of building the grid texture.
    """
    return float(zoom) >= PIXEL_GRID_MIN_ZOOM


def snap_to_pixel(x: float, y: float) -> tuple[float, float]:
    """Round a sub-pixel position to the centre of the nearest pixel.

    Pixel centres sit at integer ``+0.5`` in image space; using the
    centre means a stamped dab lands exactly on one pixel rather than
    blurring across two. Used by the brush when the user enables
    snap-to-pixel for pixel-art workflows.
    """
    return (float(int(round(float(x) - 0.5)) + 0.5),
            float(int(round(float(y) - 0.5)) + 0.5))


@dataclass(frozen=True)
class Guide:
    """One straight guide line."""

    orientation: str
    position: int
    color: tuple[int, int, int, int] = DEFAULT_GUIDE_COLOR
    visible: bool = True

    def __post_init__(self) -> None:
        if self.orientation not in GUIDE_ORIENTATIONS:
            raise ValueError(
                f"unknown guide orientation {self.orientation!r}; "
                f"expected one of {GUIDE_ORIENTATIONS}",
            )
        for component in self.color:
            if not 0 <= int(component) <= 255:
                raise ValueError(
                    f"color components must be in [0, 255], got {self.color!r}",
                )

    def to_dict(self) -> dict:
        return {
            "orientation": self.orientation,
            "position": int(self.position),
            "color": list(self.color),
            "visible": bool(self.visible),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Guide:
        if not isinstance(raw, dict):
            raise ValueError(f"guide payload must be a dict, got {type(raw).__name__}")
        orientation = str(raw.get("orientation", "vertical"))
        if orientation not in GUIDE_ORIENTATIONS:
            orientation = "vertical"
        color = raw.get("color")
        if isinstance(color, (list, tuple)) and len(color) == 4:
            color_tuple = tuple(max(0, min(255, int(c))) for c in color)
        else:
            color_tuple = DEFAULT_GUIDE_COLOR
        return cls(
            orientation=orientation,
            position=int(raw.get("position", 0)),
            color=color_tuple,   # type: ignore[arg-type]
            visible=bool(raw.get("visible", True)),
        )


@dataclass(frozen=True)
class GridSpec:
    """Pixel grid configuration.

    ``minor_interval`` is the pixel spacing between minor grid lines.
    ``major_every`` is how many minor cells fit between major lines
    (so for ``minor_interval = 10`` and ``major_every = 5``, major
    lines appear every 50 px). Setting ``major_every = 1`` hides the
    minor lines (every line is major).
    """

    minor_interval: int = 10
    major_every: int = 5
    minor_color: tuple[int, int, int, int] = DEFAULT_GRID_MINOR_COLOR
    major_color: tuple[int, int, int, int] = DEFAULT_GRID_MAJOR_COLOR
    visible: bool = True

    def __post_init__(self) -> None:
        if not MIN_GRID_INTERVAL <= int(self.minor_interval) <= MAX_GRID_INTERVAL:
            raise ValueError(
                f"minor_interval must be in "
                f"[{MIN_GRID_INTERVAL}, {MAX_GRID_INTERVAL}], "
                f"got {self.minor_interval!r}",
            )
        if int(self.major_every) <= 0:
            raise ValueError(
                f"major_every must be > 0, got {self.major_every!r}",
            )

    def to_dict(self) -> dict:
        return {
            "minor_interval": int(self.minor_interval),
            "major_every": int(self.major_every),
            "minor_color": list(self.minor_color),
            "major_color": list(self.major_color),
            "visible": bool(self.visible),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> GridSpec:
        if not isinstance(raw, dict):
            raise ValueError(
                f"grid payload must be a dict, got {type(raw).__name__}",
            )
        minor = max(
            MIN_GRID_INTERVAL,
            min(MAX_GRID_INTERVAL, int(raw.get("minor_interval", 10))),
        )
        major = max(1, int(raw.get("major_every", 5)))

        def _coerce(key, default):
            raw_color = raw.get(key)
            if isinstance(raw_color, (list, tuple)) and len(raw_color) == 4:
                try:
                    return tuple(max(0, min(255, int(c))) for c in raw_color)
                except (TypeError, ValueError):
                    return default
            return default

        return cls(
            minor_interval=minor,
            major_every=major,
            minor_color=_coerce("minor_color", DEFAULT_GRID_MINOR_COLOR),
            major_color=_coerce("major_color", DEFAULT_GRID_MAJOR_COLOR),
            visible=bool(raw.get("visible", True)),
        )


@dataclass
class GuideSet:
    """Mutable collection of guides + an optional grid spec."""

    guides: list[Guide] = field(default_factory=list)
    grid: GridSpec | None = None

    def add_guide(self, guide: Guide) -> None:
        self.guides.append(guide)

    def remove_guide(self, index: int) -> bool:
        if not 0 <= index < len(self.guides):
            return False
        del self.guides[index]
        return True

    def clear(self) -> None:
        self.guides = []
        self.grid = None


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def render_overlay(
    canvas_size: tuple[int, int],
    guide_set: GuideSet,
) -> np.ndarray:
    """Render the grid + guides as an HxWx4 RGBA overlay buffer."""
    h, w = canvas_size
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas_size must be positive, got {canvas_size!r}")
    out = np.zeros((h, w, 4), dtype=np.uint8)

    if guide_set.grid is not None and guide_set.grid.visible:
        _paint_grid(out, guide_set.grid)

    for guide in guide_set.guides:
        if not guide.visible:
            continue
        _paint_guide(out, guide)

    return out


def _paint_grid(canvas: np.ndarray, grid: GridSpec) -> None:
    h, w = canvas.shape[:2]
    minor = max(MIN_GRID_INTERVAL, int(grid.minor_interval))
    major_step = max(1, int(grid.major_every))

    minor_color = grid.minor_color
    major_color = grid.major_color

    # Vertical grid lines.
    x = 0
    line_index = 0
    while x < w:
        is_major = (line_index % major_step) == 0
        color = major_color if is_major else minor_color
        canvas[:, x] = color
        x += minor
        line_index += 1
    # Horizontal grid lines.
    y = 0
    line_index = 0
    while y < h:
        is_major = (line_index % major_step) == 0
        color = major_color if is_major else minor_color
        canvas[y, :] = color
        y += minor
        line_index += 1


def _paint_guide(canvas: np.ndarray, guide: Guide) -> None:
    h, w = canvas.shape[:2]
    pos = int(guide.position)
    if guide.orientation == "vertical":
        if 0 <= pos < w:
            canvas[:, pos] = guide.color
    elif 0 <= pos < h:
        canvas[pos, :] = guide.color
