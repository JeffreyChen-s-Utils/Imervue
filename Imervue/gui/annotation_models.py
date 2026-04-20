"""
Annotation data model + headless PIL rendering.

No Qt imports: this module can be imported from worker threads and exercised
from unit tests without a display. The interactive canvas in
``annotation_dialog.py`` has its own QPainter-based drawing path for live
preview — the two paths aim to be visually equivalent but don't share code
because QPainter and PIL's coordinate / antialiasing conventions differ
enough to make sharing brittle.
"""
from __future__ import annotations

import json
import math
import random
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import contextlib

AnnotationKind = Literal[
    "rect",
    "ellipse",
    "line",
    "arrow",
    "freehand",
    "text",
    "mosaic",
    "blur",
]

# Freehand brush presets — each one renders the same points list differently
# so the user can pick a look (pen / marker / pencil / highlighter / spray).
# Default is ``pen`` so existing annotations keep their previous appearance.
BrushType = Literal[
    "pen", "marker", "pencil", "highlighter", "spray",
    "calligraphy", "watercolor", "charcoal", "crayon",
]

ALL_BRUSHES: tuple[BrushType, ...] = (
    "pen", "marker", "pencil", "highlighter", "spray",
    "calligraphy", "watercolor", "charcoal", "crayon",
)

ALL_KINDS: tuple[AnnotationKind, ...] = (
    "rect", "ellipse", "line", "arrow",
    "freehand", "text", "mosaic", "blur",
)

# Kinds that destructively modify pixels (applied before overlay pass).
_DESTRUCTIVE: frozenset[str] = frozenset({"mosaic", "blur"})


@dataclass
class Annotation:
    kind: AnnotationKind
    points: list[tuple[int, int]] = field(default_factory=list)
    color: tuple[int, int, int, int] = (255, 0, 0, 255)
    stroke_width: int = 3
    filled: bool = False
    text: str = ""
    font_size: int = 24
    block_size: int = 16   # mosaic: block pixel size
    blur_radius: int = 10  # blur: gaussian radius
    # Freehand brush parameters. Ignored for non-freehand kinds. Defaults
    # match the original plain-pen behavior so pre-brush projects load
    # unchanged.
    brush_type: BrushType = "pen"
    opacity: int = 100       # 0..100 percent — multiplies color alpha
    spacing: int = 8         # px — only used by spray brush
    font_family: str = ""    # text: Qt font family name (empty = system default)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "points": [list(p) for p in self.points],
            "color": list(self.color),
            "stroke_width": self.stroke_width,
            "filled": self.filled,
            "text": self.text,
            "font_size": self.font_size,
            "block_size": self.block_size,
            "blur_radius": self.blur_radius,
            "brush_type": self.brush_type,
            "opacity": self.opacity,
            "spacing": self.spacing,
            "font_family": self.font_family,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Annotation:
        return cls(
            kind=d["kind"],
            points=[tuple(p) for p in d.get("points", [])],
            color=tuple(d.get("color", [255, 0, 0, 255])),
            stroke_width=int(d.get("stroke_width", 3)),
            filled=bool(d.get("filled", False)),
            text=d.get("text", ""),
            font_size=int(d.get("font_size", 24)),
            block_size=int(d.get("block_size", 16)),
            blur_radius=int(d.get("blur_radius", 10)),
            brush_type=d.get("brush_type", "pen"),
            opacity=int(d.get("opacity", 100)),
            spacing=int(d.get("spacing", 8)),
            font_family=d.get("font_family", ""),
            id=d.get("id") or uuid.uuid4().hex[:12],
        )

    def bounding_box(self) -> tuple[int, int, int, int]:
        """Return (x1, y1, x2, y2) covering all points (normalized so x1<=x2)."""
        if not self.points:
            return (0, 0, 0, 0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def normalized_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) — positive width/height — from the bounding box."""
        x1, y1, x2, y2 = self.bounding_box()
        return (x1, y1, x2 - x1, y2 - y1)


@dataclass
class AnnotationProject:
    """Serializable project: source path + image size + annotation list.

    Written by "Save Project..." in the annotation dialog. The schema carries
    an explicit ``version`` so future loaders can detect older / newer files
    and decide how to handle unknown fields instead of crashing.
    """
    version: int = 1
    source_path: str = ""
    source_size: tuple[int, int] = (0, 0)
    annotations: list[Annotation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_path": self.source_path,
            "source_size": list(self.source_size),
            "annotations": [a.to_dict() for a in self.annotations],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnnotationProject:
        return cls(
            version=int(d.get("version", 1)),
            source_path=d.get("source_path", ""),
            source_size=tuple(d.get("source_size", [0, 0])),
            annotations=[Annotation.from_dict(a) for a in d.get("annotations", [])],
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> AnnotationProject:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# Font resolution
# ---------------------------------------------------------------------------

_FONT_CACHE: dict[tuple[str, int], ImageFont.ImageFont] = {}


def _system_font_candidates() -> list[str]:
    if sys.platform == "win32":
        return [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
        ]
    if sys.platform == "darwin":
        return [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    # Linux
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    ]


def _resolve_font_path(family: str) -> str | None:
    """Try to find a .ttf/.ttc file for a given font family name on Windows."""
    if not family or sys.platform != "win32":
        return None
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        )
    except OSError:
        return None
    try:
        return _scan_font_registry(winreg, key, family.lower())
    finally:
        with contextlib.suppress(OSError):
            winreg.CloseKey(key)


def _scan_font_registry(winreg, key, family_lower: str) -> str | None:
    i = 0
    while True:
        try:
            name, value, _ = winreg.EnumValue(key, i)
        except OSError:
            return None
        i += 1
        if family_lower not in name.lower():
            continue
        resolved = _resolve_font_value(value)
        if resolved:
            return resolved


def _resolve_font_value(value: str) -> str | None:
    p = Path(value)
    if not p.is_absolute():
        p = Path(r"C:\Windows\Fonts") / p
    return str(p) if p.exists() else None


def _get_font(size: int, family: str = "") -> ImageFont.ImageFont:
    cache_key = (family, size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]
    font: ImageFont.ImageFont | None = None
    # Try the requested family first
    if family:
        resolved = _resolve_font_path(family)
        if resolved:
            with contextlib.suppress(OSError):
                font = ImageFont.truetype(resolved, size)
    # Fallback to system defaults
    if font is None:
        for cand in _system_font_candidates():
            try:
                font = ImageFont.truetype(cand, size)
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = font
    return font


# ---------------------------------------------------------------------------
# Baking (PIL, headless-safe)
# ---------------------------------------------------------------------------

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
    rng = random.Random(hash(ann.id) & 0xFFFFFFFF)

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
    rng = random.Random(hash(ann.id) & 0xFFFFFFFF)
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
    rng = random.Random(hash(ann.id) & 0xFFFFFFFF)
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
    rng = random.Random(hash(ann.id) & 0xFFFFFFFF)
    # Draw multiple thin lines with slight offsets for a waxy texture
    for offset in range(3):
        jittered = [
            (x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
            for x, y in ann.points
        ]
        w = max(1, width - offset)
        draw.line(jittered, fill=color, width=w, joint="curve")


def _draw_text(draw: ImageDraw.ImageDraw, ann: Annotation) -> None:
    if not ann.text or not ann.points:
        return
    anchor = ann.points[0]
    font = _get_font(max(6, ann.font_size), ann.font_family)
    draw.text(anchor, ann.text, fill=ann.color, font=font)
