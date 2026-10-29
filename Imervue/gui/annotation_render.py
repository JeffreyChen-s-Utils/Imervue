"""
Headless PIL rendering of annotations.

``bake`` applies the pixel-destructive kinds (mosaic, blur) to a copy of the
base image, then composites every stroke, fill and text overlay on top. No Qt
imports, so it runs on worker threads and in tests without a display.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter

from Imervue.gui.annotation_brushes import _draw_freehand
from Imervue.gui.annotation_fonts import _get_font

if TYPE_CHECKING:
    from Imervue.gui.annotation_models import Annotation

# Kinds that destructively modify pixels (applied before overlay pass).
_DESTRUCTIVE: frozenset[str] = frozenset({"mosaic", "blur"})


def bake(base: Image.Image, annotations: list[Annotation]) -> Image.Image:
    """Return a new RGBA image with all annotations baked in.

    Two passes:
      1. Apply pixel-destructive ops (mosaic, blur) to a working copy.
      2. Composite stroke/fill/text overlays on top via alpha compositing.

    The input image is not modified.
    """
    working = base.convert("RGBA") if base.mode != "RGBA" else base.copy()

    # Pass 1 — destructive, in-place on the working copy
    for ann in annotations:
        if ann.kind == "mosaic":
            _apply_mosaic(working, ann)
        elif ann.kind == "blur":
            _apply_blur(working, ann)

    # Pass 2 — overlays on a transparent layer, then alpha composite.
    # A separate layer lets partially-transparent colors blend correctly
    # instead of accumulating on already-drawn strokes.
    overlay = Image.new("RGBA", working.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for ann in annotations:
        if ann.kind in _DESTRUCTIVE:
            continue
        _draw_annotation(draw, ann)

    return Image.alpha_composite(working, overlay)


def _clamp_rect(img: Image.Image, x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    x2 = min(img.width, x + w)
    y2 = min(img.height, y + h)
    x = max(0, x)
    y = max(0, y)
    return x, y, max(0, x2 - x), max(0, y2 - y)


def _apply_mosaic(img: Image.Image, ann: Annotation) -> None:
    x, y, w, h = ann.normalized_rect()
    x, y, w, h = _clamp_rect(img, x, y, w, h)
    if w <= 0 or h <= 0:
        return
    block = max(2, ann.block_size)
    region = img.crop((x, y, x + w, y + h))
    small = region.resize(
        (max(1, w // block), max(1, h // block)),
        resample=Image.Resampling.BILINEAR,
    )
    mosaic = small.resize((w, h), resample=Image.Resampling.NEAREST)
    img.paste(mosaic, (x, y))


def _apply_blur(img: Image.Image, ann: Annotation) -> None:
    x, y, w, h = ann.normalized_rect()
    x, y, w, h = _clamp_rect(img, x, y, w, h)
    if w <= 0 or h <= 0:
        return
    radius = max(1, ann.blur_radius)
    region = img.crop((x, y, x + w, y + h))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))
    img.paste(blurred, (x, y))


def _draw_annotation(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    if ann.kind == "rect":
        _draw_rect(draw, ann)
    elif ann.kind == "ellipse":
        _draw_ellipse(draw, ann)
    elif ann.kind == "line":
        _draw_line(draw, ann)
    elif ann.kind == "arrow":
        _draw_arrow(draw, ann)
    elif ann.kind == "freehand":
        _draw_freehand(draw, ann)
    elif ann.kind == "text":
        _draw_text(draw, ann)


def _draw_rect(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    x1, y1, x2, y2 = ann.bounding_box()
    if ann.filled:
        draw.rectangle((x1, y1, x2, y2), fill=ann.color)
    else:
        draw.rectangle((x1, y1, x2, y2), outline=ann.color, width=ann.stroke_width)


def _draw_ellipse(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    x1, y1, x2, y2 = ann.bounding_box()
    if ann.filled:
        draw.ellipse((x1, y1, x2, y2), fill=ann.color)
    else:
        draw.ellipse((x1, y1, x2, y2), outline=ann.color, width=ann.stroke_width)


def _draw_line(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    if len(ann.points) < 2:
        return
    draw.line([ann.points[0], ann.points[-1]],
              fill=ann.color, width=ann.stroke_width)


def _draw_arrow(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    if len(ann.points) < 2:
        return
    sx, sy = ann.points[0]
    ex, ey = ann.points[-1]
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length < 1:
        return
    head_len = max(10, ann.stroke_width * 5)
    head_half = max(6, ann.stroke_width * 3)
    ux, uy = dx / length, dy / length
    # Stop the line shaft 60% into the arrowhead so they overlap cleanly
    line_end = (ex - ux * head_len * 0.6, ey - uy * head_len * 0.6)
    draw.line([(sx, sy), line_end], fill=ann.color, width=ann.stroke_width)
    base_center = (ex - ux * head_len, ey - uy * head_len)
    # Perpendicular unit vector
    px, py = -uy, ux
    p1 = (base_center[0] + px * head_half, base_center[1] + py * head_half)
    p2 = (base_center[0] - px * head_half, base_center[1] - py * head_half)
    draw.polygon([(ex, ey), p1, p2], fill=ann.color, outline=ann.color)


def _draw_text(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    if not ann.text or not ann.points:
        return
    anchor = ann.points[0]
    font = _get_font(max(6, ann.font_size), ann.font_family)
    draw.text(anchor, ann.text, fill=ann.color, font=font)
