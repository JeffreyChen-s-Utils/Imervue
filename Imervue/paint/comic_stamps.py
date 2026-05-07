"""Programmatic stamp generators for comic / manga elements.

MediBang Paint Pro ships a stamp library of speech balloons, sound
bursts, and panel borders so a comic artist can drop a pre-built
shape onto the page in one click. We mirror the affordance with a
small set of *generators* — pure functions that return RGBA uint8
buffers — rather than ship binary SVG/PNG resources, so the catalog
scales with the requested size and re-renders crisp at any zoom.

Each generator obeys the same protocol:

* ``size`` parameters in pixels.
* Foreground (``fg``) draws the line; background (``bg``) fills the
  interior. ``bg=None`` produces a transparent fill so balloons can
  sit over coloured panels without clobbering the underneath.
* ``line_px`` controls outline thickness.
* The result is HxWx4 uint8 RGBA, fully transparent outside the
  shape, fully opaque on the line, and ``bg`` alpha on the inside.

Generators are listed in :data:`STAMP_LIBRARY` together with a
locale-key for the user-visible name and a thumbnail-friendly size,
which the StampDock reads when populating its grid.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

RGBA = tuple[int, int, int, int]
RGB = tuple[int, int, int]

# Default ink + paper for every generator. Comic balloons are
# black-on-white by convention; the user can recolour later via a
# colour-replace pass on the inserted layer.
_INK: RGBA = (0, 0, 0, 255)
_PAPER: RGBA = (255, 255, 255, 255)


@dataclass(frozen=True)
class Stamp:
    """Metadata + generator for one entry in the stamp library."""

    key: str               # i18n key (paint_stamp_<id>)
    fallback_name: str     # English fallback shown if the key is missing
    kind: str              # "balloon" | "burst" | "panel"
    generator: Callable[..., np.ndarray]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def oval_balloon(
    width: int, height: int, *,
    fg: RGBA = _INK, bg: RGBA | None = _PAPER, line_px: int = 3,
) -> np.ndarray:
    """Plain elliptical speech balloon with a downward-pointing tail."""
    img = _new_canvas(width, height)
    draw = ImageDraw.Draw(img)
    bbox = (line_px, line_px, width - line_px - 1, int(height * 0.78))
    fill = bg if bg is not None else (0, 0, 0, 0)
    draw.ellipse(bbox, fill=fill, outline=fg, width=line_px)
    # Tail — a short triangle hanging off the bottom-left of the oval.
    cx = int(width * 0.35)
    top_y = int(height * 0.74)
    tail = [
        (cx - int(width * 0.06), top_y),
        (cx + int(width * 0.06), top_y),
        (int(width * 0.30), height - line_px - 1),
    ]
    draw.polygon(tail, fill=fill, outline=fg)
    # Erase the part of the oval outline that crosses the tail's mouth
    # so the two shapes look fused rather than crossed.
    if bg is not None:
        draw.line([tail[0], tail[1]], fill=bg, width=line_px)
    return np.asarray(img, dtype=np.uint8).copy()


def rect_balloon(
    width: int, height: int, *,
    fg: RGBA = _INK, bg: RGBA | None = _PAPER, line_px: int = 3,
    radius: int = 12,
) -> np.ndarray:
    """Rounded-rectangle speech balloon — common for narration boxes."""
    img = _new_canvas(width, height)
    draw = ImageDraw.Draw(img)
    bbox = (line_px, line_px, width - line_px - 1, height - line_px - 1)
    fill = bg if bg is not None else (0, 0, 0, 0)
    draw.rounded_rectangle(
        bbox, radius=radius, fill=fill, outline=fg, width=line_px,
    )
    return np.asarray(img, dtype=np.uint8).copy()


def cloud_balloon(
    width: int, height: int, *,
    fg: RGBA = _INK, bg: RGBA | None = _PAPER,
    line_px: int = 3, lobes: int = 12,
) -> np.ndarray:
    """Thought-cloud balloon — N circular lobes around an ellipse rim."""
    img = _new_canvas(width, height)
    draw = ImageDraw.Draw(img)
    cx = width / 2.0
    cy = height * 0.45
    rx = width * 0.4
    ry = height * 0.32
    fill = bg if bg is not None else (0, 0, 0, 0)
    # Inner blob first (filled) so lobes overlap with the same fill.
    inner_pad = int(min(rx, ry) * 0.55)
    draw.ellipse(
        (cx - rx + inner_pad, cy - ry + inner_pad,
         cx + rx - inner_pad, cy + ry - inner_pad),
        fill=fill, outline=None,
    )
    lobe_r = max(line_px * 2, int(min(rx, ry) * 0.30))
    lobes = max(6, int(lobes))
    for i in range(lobes):
        angle = (i / lobes) * 2 * math.pi
        lx = cx + rx * math.cos(angle)
        ly = cy + ry * math.sin(angle)
        draw.ellipse(
            (lx - lobe_r, ly - lobe_r, lx + lobe_r, ly + lobe_r),
            fill=fill, outline=fg, width=line_px,
        )
    # Two tail bubbles below the cloud, shrinking — classic thought
    # bubble convention.
    bubble1 = int(lobe_r * 0.6)
    bubble2 = int(lobe_r * 0.35)
    bx, by = cx - rx * 0.5, height - bubble1 * 2 - line_px
    draw.ellipse(
        (bx - bubble1, by - bubble1, bx + bubble1, by + bubble1),
        fill=fill, outline=fg, width=line_px,
    )
    draw.ellipse(
        (bx - bubble2 + bubble1, height - bubble2 * 2 - line_px,
         bx + bubble2 + bubble1, height - line_px - 1),
        fill=fill, outline=fg, width=line_px,
    )
    return np.asarray(img, dtype=np.uint8).copy()


def jagged_shout(
    width: int, height: int, *,
    fg: RGBA = _INK, bg: RGBA | None = _PAPER,
    line_px: int = 3, points: int = 16,
) -> np.ndarray:
    """Spike-edged shouting / explosion balloon."""
    img = _new_canvas(width, height)
    draw = ImageDraw.Draw(img)
    cx = width / 2.0
    cy = height / 2.0
    rx_outer = (width / 2.0) - line_px
    ry_outer = (height / 2.0) - line_px
    rx_inner = rx_outer * 0.72
    ry_inner = ry_outer * 0.72
    points = max(8, int(points))
    coords: list[tuple[float, float]] = []
    for i in range(points * 2):
        angle = (i / (points * 2)) * 2 * math.pi
        is_outer = i % 2 == 0
        rx = rx_outer if is_outer else rx_inner
        ry = ry_outer if is_outer else ry_inner
        coords.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    fill = bg if bg is not None else (0, 0, 0, 0)
    draw.polygon(coords, fill=fill, outline=fg)
    # PIL polygon outline is 1px; redraw the edge wider for parity.
    if line_px > 1:
        edge = list(coords) + [coords[0]]
        draw.line(edge, fill=fg, width=line_px)
    return np.asarray(img, dtype=np.uint8).copy()


def sound_burst(
    size: int, *,
    fg: RGBA = _INK, bg: RGBA | None = None,
    line_px: int = 3, rays: int = 14,
) -> np.ndarray:
    """Radial sound-effect burst — rays from a central blank dot."""
    img = _new_canvas(size, size)
    draw = ImageDraw.Draw(img)
    cx = cy = size / 2.0
    r_inner = size * 0.10
    r_outer = (size / 2.0) - line_px
    rays = max(6, int(rays))
    if bg is not None:
        draw.ellipse(
            (cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner),
            fill=bg, outline=fg, width=line_px,
        )
    for i in range(rays):
        angle = (i / rays) * 2 * math.pi
        x0 = cx + r_inner * math.cos(angle)
        y0 = cy + r_inner * math.sin(angle)
        x1 = cx + r_outer * math.cos(angle)
        y1 = cy + r_outer * math.sin(angle)
        draw.line((x0, y0, x1, y1), fill=fg, width=line_px)
    return np.asarray(img, dtype=np.uint8).copy()


def panel_border(
    width: int, height: int, *,
    fg: RGBA = _INK, bg: RGBA | None = None, line_px: int = 5,
) -> np.ndarray:
    """Plain rectangular panel outline — for laying out manga grids."""
    img = _new_canvas(width, height)
    draw = ImageDraw.Draw(img)
    bbox = (line_px // 2, line_px // 2,
            width - 1 - line_px // 2, height - 1 - line_px // 2)
    fill = bg if bg is not None else (0, 0, 0, 0)
    draw.rectangle(bbox, fill=fill, outline=fg, width=line_px)
    return np.asarray(img, dtype=np.uint8).copy()


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


STAMP_LIBRARY: tuple[Stamp, ...] = (
    Stamp("paint_stamp_oval_balloon", "Oval balloon", "balloon", oval_balloon),
    Stamp("paint_stamp_rect_balloon", "Rect balloon", "balloon", rect_balloon),
    Stamp("paint_stamp_cloud_balloon", "Thought cloud", "balloon", cloud_balloon),
    Stamp("paint_stamp_jagged_shout", "Shout balloon", "balloon", jagged_shout),
    Stamp("paint_stamp_sound_burst", "Sound burst", "burst", sound_burst),
    Stamp("paint_stamp_panel_border", "Panel border", "panel", panel_border),
)


def stamp_by_key(key: str) -> Stamp:
    """Return the stamp registered under ``key`` or raise KeyError."""
    for stamp in STAMP_LIBRARY:
        if stamp.key == key:
            return stamp
    raise KeyError(key)


def render_stamp(key: str, width: int, height: int) -> np.ndarray:
    """Resolve and invoke a stamp generator with sensible defaults.

    ``sound_burst`` is square-only so the smaller of width/height is
    used. Other generators take full ``width`` x ``height``.
    """
    stamp = stamp_by_key(key)
    if stamp.kind == "burst":
        size = min(int(width), int(height))
        return stamp.generator(size)
    return stamp.generator(int(width), int(height))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _new_canvas(width: int, height: int) -> Image.Image:
    """Fresh transparent RGBA Pillow canvas at the requested size."""
    if int(width) <= 0 or int(height) <= 0:
        raise ValueError(
            f"stamp dimensions must be positive, got {(width, height)}",
        )
    return Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
