"""
Freehand brush presets for the headless PIL bake.

Each brush renders the same points list differently (pen, marker, pencil,
highlighter, spray, calligraphy, watercolor, charcoal, crayon). The jittered
brushes scatter their marks from an RNG seeded by ``jitter_seed`` so the same
annotation always bakes to the same pixels.
"""
from __future__ import annotations

import math
import random
import zlib
from typing import TYPE_CHECKING

from PIL import ImageDraw

if TYPE_CHECKING:
    from Imervue.gui.annotation_models import Annotation


def jitter_seed(annotation_id: str) -> int:
    """Stable 32-bit RNG seed for an annotation's brush jitter.

    Spray, charcoal and crayon strokes scatter their marks from a seeded RNG so
    the same annotation always looks the same. ``hash()`` cannot seed it: Python
    randomises ``str`` hashes per process, so a reopened project would change.
    """
    return zlib.crc32(annotation_id.encode("utf-8"))


def _apply_opacity(color: tuple[int, int, int, int], opacity: int) -> tuple[int, int, int, int]:
    """Multiply the alpha channel of ``color`` by ``opacity`` (0..100)."""
    opacity = max(0, min(100, int(opacity)))
    r, g, b, a = color
    return (r, g, b, int(a * opacity / 100))


def _draw_freehand(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    if len(ann.points) < 2:
        return
    brush = getattr(ann, "brush_type", "pen")
    _FREEHAND_DISPATCH = {
        "marker": _draw_freehand_marker,
        "pencil": _draw_freehand_pencil,
        "highlighter": _draw_freehand_highlighter,
        "spray": _draw_freehand_spray,
        "calligraphy": _draw_freehand_calligraphy,
        "watercolor": _draw_freehand_watercolor,
        "charcoal": _draw_freehand_charcoal,
        "crayon": _draw_freehand_crayon,
    }
    fn = _FREEHAND_DISPATCH.get(brush, _draw_freehand_pen)
    fn(draw, ann)


def _draw_freehand_pen(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    color = _apply_opacity(ann.color, ann.opacity)
    draw.line(list(ann.points), fill=color,
              width=ann.stroke_width, joint="curve")


def _draw_freehand_marker(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    # Marker: thicker stroke, slightly translucent so overlaps blend.
    r, g, b, a = ann.color
    base = (r, g, b, int(a * 0.7))
    color = _apply_opacity(base, ann.opacity)
    width = max(1, int(ann.stroke_width * 1.8))
    draw.line(list(ann.points), fill=color, width=width, joint="curve")


def _draw_freehand_pencil(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    # Pencil: thin, slightly faded hairline stroke.
    r, g, b, a = ann.color
    base = (r, g, b, int(a * 0.85))
    color = _apply_opacity(base, ann.opacity)
    width = max(1, ann.stroke_width // 2)
    draw.line(list(ann.points), fill=color, width=width, joint="curve")


def _draw_freehand_highlighter(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    # Highlighter: very wide, very translucent — stacks like ink.
    r, g, b, a = ann.color
    base = (r, g, b, int(a * 0.35))
    color = _apply_opacity(base, ann.opacity)
    width = max(1, int(ann.stroke_width * 3))
    draw.line(list(ann.points), fill=color, width=width, joint="curve")


def _draw_freehand_spray(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    # Spray: scatter small dots around each sampled point along the path.
    # Seeded RNG so repeated bakes of the same annotation match.
    color = _apply_opacity(ann.color, ann.opacity)
    radius = max(1, ann.stroke_width)
    spread = max(2, ann.stroke_width * 3)
    spacing = max(1, int(ann.spacing))
    rng = random.Random(jitter_seed(ann.id))

    # Walk the polyline at approximately ``spacing`` pixel intervals so that
    # stroke speed does not change the dot density.
    pts = ann.points
    samples: list[tuple[float, float]] = []
    accumulated = 0.0
    samples.append((float(pts[0][0]), float(pts[0][1])))
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len <= 0:
            continue
        ux, uy = (x2 - x1) / seg_len, (y2 - y1) / seg_len
        remaining = seg_len
        while accumulated + remaining >= spacing:
            step = spacing - accumulated
            cx = x1 + ux * (seg_len - remaining + step)
            cy = y1 + uy * (seg_len - remaining + step)
            samples.append((cx, cy))
            remaining -= step
            accumulated = 0.0
        accumulated += remaining

    dots_per_sample = max(4, ann.stroke_width * 2)
    for cx, cy in samples:
        for _ in range(dots_per_sample):
            # Rejection sample to a disc so the spray looks round, not square.
            while True:
                ox = rng.uniform(-spread, spread)
                oy = rng.uniform(-spread, spread)
                if ox * ox + oy * oy <= spread * spread:
                    break
            px_ = cx + ox
            py_ = cy + oy
            draw.ellipse(
                (px_ - radius / 2, py_ - radius / 2,
                 px_ + radius / 2, py_ + radius / 2),
                fill=color,
            )


def _draw_freehand_calligraphy(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    """Calligraphy: variable width based on stroke direction (angled nib)."""
    color = _apply_opacity(ann.color, ann.opacity)
    pts = ann.points
    base_w = max(1, ann.stroke_width)
    nib_angle = math.pi / 4  # 45-degree nib
    cos_a, sin_a = math.cos(nib_angle), math.sin(nib_angle)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        dx, dy = x2 - x1, y2 - y1
        seg_len = math.hypot(dx, dy)
        if seg_len < 0.5:
            continue
        # Project direction onto nib normal to vary width
        ux, uy = dx / seg_len, dy / seg_len
        proj = abs(ux * cos_a + uy * sin_a)
        w = max(1, int(base_w * (0.3 + 0.7 * proj)))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=w)


def _draw_freehand_watercolor(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    """Watercolor: wide, very translucent, with slight random edge bleeding."""
    r, g, b, a = ann.color
    base = (r, g, b, int(a * 0.2))
    color = _apply_opacity(base, ann.opacity)
    width = max(1, int(ann.stroke_width * 2.5))
    rng = random.Random(jitter_seed(ann.id))
    # Draw multiple slightly offset passes for a wet-edge look
    for _ in range(3):
        offset_pts = [
            (x + rng.gauss(0, width * 0.15), y + rng.gauss(0, width * 0.15))
            for x, y in ann.points
        ]
        draw.line(offset_pts, fill=color, width=width, joint="curve")


def _draw_freehand_charcoal(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    """Charcoal: rough, textured stroke with scattered dots along the path."""
    color = _apply_opacity(ann.color, ann.opacity)
    width = max(1, int(ann.stroke_width * 1.2))
    rng = random.Random(jitter_seed(ann.id))
    # Main stroke
    draw.line(list(ann.points), fill=color, width=width, joint="curve")
    # Scatter texture dots along the path
    spread = max(2, width)
    for x, y in ann.points[::3]:
        for _ in range(2):
            ox = rng.gauss(0, spread * 0.5)
            oy = rng.gauss(0, spread * 0.5)
            r2 = max(0.5, width * 0.3)
            draw.ellipse(
                (x + ox - r2, y + oy - r2, x + ox + r2, y + oy + r2),
                fill=color,
            )


def _draw_freehand_crayon(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    """Crayon: medium width, slightly rough, with gaps in coverage."""
    r, g, b, a = ann.color
    base = (r, g, b, int(a * 0.8))
    color = _apply_opacity(base, ann.opacity)
    width = max(1, int(ann.stroke_width * 1.5))
    rng = random.Random(jitter_seed(ann.id))
    # Draw multiple thin lines with slight offsets for a waxy texture
    for offset in range(3):
        jittered = [
            (x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
            for x, y in ann.points
        ]
        w = max(1, width - offset)
        draw.line(jittered, fill=color, width=w, joint="curve")
