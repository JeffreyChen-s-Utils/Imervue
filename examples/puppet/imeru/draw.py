"""Vector-style drawing primitives for the Imeru layers: Bézier paths, tapered strokes, fills.

Everything is drawn at ``S`` times the canvas size and downsampled once per layer, so
edges come out anti-aliased. Coordinates are canvas pixels of the final 1024 x 1536 canvas.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H, S = 1024, 1536, 3


def bez(p0, c0, c1, p1, n: int = 40) -> list[tuple[float, float]]:
    """Points along a cubic Bézier curve."""
    t = np.linspace(0.0, 1.0, n)[:, None]
    p0, c0, c1, p1 = (np.asarray(p, dtype=float) for p in (p0, c0, c1, p1))
    pts = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c0 + 3 * (1 - t) * t * t * c1 + t**3 * p1
    return [tuple(p) for p in pts]


def chain(*parts) -> list[tuple[float, float]]:
    """Concatenate point lists, dropping a repeated joint point."""
    out: list[tuple[float, float]] = []
    for part in parts:
        points = list(part)
        if out and np.allclose(out[-1], points[0]):
            points = points[1:]
        out.extend(points)
    return out


def mirror(points) -> list[tuple[float, float]]:
    """Reflect points about the canvas's vertical centre line."""
    return [(W - x, y) for x, y in points]


def ellipse_pts(cx, cy, rx, ry, n: int = 80, rot: float = 0.0) -> list[tuple[float, float]]:
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x, y = rx * np.cos(a), ry * np.sin(a)
    c, s = np.cos(rot), np.sin(rot)
    return [(cx + xi * c - yi * s, cy + xi * s + yi * c) for xi, yi in zip(x, y, strict=True)]


def new_mask() -> Image.Image:
    return Image.new("L", (W * S, H * S), 0)


def new_layer() -> Image.Image:
    return Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))


def _scaled(points):
    return [(x * S, y * S) for x, y in points]


def poly(points, mask: Image.Image | None = None, value: int = 255) -> Image.Image:
    mask = mask if mask is not None else new_mask()
    ImageDraw.Draw(mask).polygon(_scaled(points), fill=value)
    return mask


def ribbon_outline(points, widths) -> list[tuple[float, float]]:
    """Polygon of a stroke along *points* whose width at each point is *widths* (canvas px)."""
    p = np.asarray(points, dtype=float)
    d = np.gradient(p, axis=0)
    n = np.stack([-d[:, 1], d[:, 0]], axis=1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    w = np.asarray(widths, dtype=float)[:, None] / 2
    left, right = p + n * w, p - n * w
    return [tuple(q) for q in np.concatenate([left, right[::-1]])]


def taper(n: int, w0: float, wmax: float, w1: float, peak: float = 0.5) -> np.ndarray:
    """Width profile: *w0* at the start, *wmax* at *peak* (0..1), *w1* at the end, smooth."""
    t = np.linspace(0, 1, n)
    rise = np.clip(t / max(peak, 1e-6), 0, 1)
    fall = np.clip((1 - t) / max(1 - peak, 1e-6), 0, 1)
    up = w0 + (wmax - w0) * np.sin(rise * np.pi / 2)
    down = w1 + (wmax - w1) * np.sin(fall * np.pi / 2)
    return np.where(t <= peak, up, down)


def stroke(points, widths, mask: Image.Image | None = None) -> Image.Image:
    mask = mask if mask is not None else new_mask()
    draw = ImageDraw.Draw(mask)
    draw.polygon(_scaled(ribbon_outline(points, widths)), fill=255)
    return mask


def line(points, width: float, mask: Image.Image | None = None) -> Image.Image:
    """An even-width stroke with round ends."""
    mask = mask if mask is not None else new_mask()
    draw = ImageDraw.Draw(mask)
    pts = _scaled(points)
    w = max(1, int(round(width * S)))
    draw.line(pts, fill=255, width=w, joint="curve")
    r = w / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return mask


def blur(mask: Image.Image, radius: float) -> Image.Image:
    return mask.filter(ImageFilter.GaussianBlur(radius * S))


def clip(mask: Image.Image, by: Image.Image) -> Image.Image:
    return ImageChops.multiply(mask, by)


def scale_mask(mask: Image.Image, factor: float) -> Image.Image:
    return mask.point(lambda v: int(v * factor))


def _rgba(color) -> tuple[int, int, int, int]:
    if isinstance(color, str):
        color = color.lstrip("#")
        rgb = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
        return (*rgb, 255)
    return tuple(color) if len(color) == 4 else (*color, 255)


def paint(layer: Image.Image, mask: Image.Image, color, alpha: float = 1.0) -> None:
    """Composite a solid *color* through *mask* onto *layer*."""
    box = mask.getbbox()
    if box is None:
        return
    region = mask.crop(box)
    if alpha != 1.0:
        region = scale_mask(region, alpha)
    solid = Image.new("RGBA", region.size, _rgba(color))
    solid.putalpha(ImageChops.multiply(region, Image.new("L", region.size, _rgba(color)[3])))
    layer.alpha_composite(solid, dest=box[:2])


def paint_gradient(
    layer: Image.Image, mask: Image.Image, p0, c0, p1, c1, alpha: float = 1.0
) -> None:
    """Linear gradient from colour *c0* at canvas point *p0* to *c1* at *p1*, through *mask*."""
    box = mask.getbbox()
    if box is None:
        return
    x0, y0, x1, y1 = box
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32) / S
    (ax, ay), (bx, by) = p0, p1
    dx, dy = bx - ax, by - ay
    t = ((xs - ax) * dx + (ys - ay) * dy) / max(dx * dx + dy * dy, 1e-9)
    t = np.clip(t, 0, 1)[..., None]
    a, b = np.asarray(_rgba(c0), np.float32), np.asarray(_rgba(c1), np.float32)
    rgba = a + (b - a) * t
    region = np.asarray(mask.crop(box), np.float32)[..., None] / 255.0 * alpha
    rgba[..., 3:4] *= region
    layer.alpha_composite(Image.fromarray(rgba.astype(np.uint8), "RGBA"), dest=(x0, y0))


def finish(layer: Image.Image) -> np.ndarray:
    """Downsample a supersampled layer to the canvas: an HxWx4 uint8 array."""
    small = layer.convert("RGBa").resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
    return np.asarray(small, dtype=np.uint8)
