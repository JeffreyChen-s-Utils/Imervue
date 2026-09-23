"""Censor geometry and rendering shared by the in-app detection and ``_runner.py``.

``_runner.py`` runs in an external Python for the frozen build, where the Qt
plugin package cannot be imported, so it loads this module as a plain sibling
file. In-app code imports it as ``safety_review._censor_core``. Keep it free of
Qt and Imervue imports: only the standard library, Pillow and NumPy.
"""
from __future__ import annotations

import os

if __package__:   # imported as part of the plugin package
    from safety_review._constants import (
        ELLIPSE_COVER_FRAC,
        MODE_ANIME,
        MODE_REAL,
        SHAPE_ELLIPSE,
        SHAPE_PRECISE,
        SHAPE_RECT,
        STYLE_BLACK,
        STYLE_BLUR,
        STYLE_MOSAIC,
    )
else:             # loaded next to _runner.py by the external Python
    from _constants import (
        ELLIPSE_COVER_FRAC,
        MODE_ANIME,
        MODE_REAL,
        SHAPE_ELLIPSE,
        SHAPE_PRECISE,
        SHAPE_RECT,
        STYLE_BLACK,
        STYLE_BLUR,
        STYLE_MOSAIC,
    )

# Anime-color heuristic threshold — fewer unique quantized colours than this
# marks an image as an illustration rather than a photo.
_ANIME_COLOR_THRESHOLD = 1500

# 8-bit channels are quantized down to 5 bits before the distinct-colour
# count so near-identical shades (JPEG noise, soft gradients) collapse
# together instead of making every photo look like a photo by default.
_QUANTIZE_BITS = 3
_QUANTIZE_LEVEL_BITS = 8 - _QUANTIZE_BITS

_MERGE_GAP_FRAC = 0.4  # bridge boxes within 40% of the median box edge


def _detect_image_mode(src: str) -> str:
    """Heuristic: anime/illustration images have fewer unique quantized colors."""
    import numpy as np
    from PIL import Image
    with Image.open(src) as opened:
        img = opened.convert("RGB")
    img = img.resize((128, 128), Image.Resampling.BILINEAR)
    # Vectorised rather than a per-pixel loop over ``getdata()``: that
    # API is deprecated for removal in Pillow 14, and 16k tuples through
    # the interpreter cost far more than the whole resize before them.
    # Each channel is 5 bits after the shift, so packing them into one
    # integer makes the distinct-colour count a single 1-D unique().
    channels = np.asarray(img, dtype=np.uint32) >> _QUANTIZE_BITS
    packed = (
        (channels[..., 0] << (2 * _QUANTIZE_LEVEL_BITS))
        | (channels[..., 1] << _QUANTIZE_LEVEL_BITS)
        | channels[..., 2]
    )
    unique_colors = int(np.unique(packed).size)
    return MODE_ANIME if unique_colors < _ANIME_COLOR_THRESHOLD else MODE_REAL


def _expand_box(x1, y1, x2, y2, padding: int, expand_pct: int,
                 *, iw: int, ih: int):
    """Expand a bounding box by fixed padding AND/OR percentage of box size."""
    bw = x2 - x1
    bh = y2 - y1
    # Percentage-based expansion (% of the box's own size)
    if expand_pct > 0:
        ex = int(bw * expand_pct / 100)
        ey = int(bh * expand_pct / 100)
        x1 -= ex
        y1 -= ey
        x2 += ex
        y2 += ey
    # Fixed-pixel padding (additive)
    if padding > 0:
        x1 -= padding
        y1 -= padding
        x2 += padding
        y2 += padding
    return max(0, x1), max(0, y1), min(iw, x2), min(ih, y2)


def _censored_region(region, w, h, block_size, style):
    """Return the censored copy of *region* (same size), for the chosen style."""
    from PIL import Image as _Img
    if style == STYLE_BLACK:
        return _Img.new(region.mode, (w, h), 0)
    if style == STYLE_BLUR:
        from PIL import ImageFilter
        radius = max(max(w, h) // 5, 10)
        return region.filter(ImageFilter.GaussianBlur(radius=radius))
    # mosaic (default)
    bs = max(2, block_size)
    small = region.resize(
        (max(1, w // bs), max(1, h // bs)),
        resample=_Img.Resampling.BILINEAR,
    )
    return small.resize((w, h), resample=_Img.Resampling.NEAREST)


def _ellipse_mask(w, h, cover: float = ELLIPSE_COVER_FRAC):
    """L-mode mask (255 inside an inset ellipse, 0 outside).

    The ellipse is inset to *cover* of each axis and centred, so it hugs the
    middle of the box rather than bulging out to touch all four edges — the
    "tighter" the option promises. ``cover`` is clamped to ``(0, 1]``; a box so
    small the inset would collapse it falls back to the full inscribed ellipse
    so a tiny detection is never left uncensored.
    """
    from PIL import Image as _Img, ImageDraw
    mask = _Img.new("L", (w, h), 0)
    cover = min(1.0, max(0.05, cover))
    margin_x = int((w - 1) * (1.0 - cover) / 2)
    margin_y = int((h - 1) * (1.0 - cover) / 2)
    x2 = w - 1 - margin_x
    y2 = h - 1 - margin_y
    if x2 <= margin_x or y2 <= margin_y:
        # Box too small (e.g. a 1-px edge) to inscribe an inset ellipse — fill
        # it solid so a tiny region is still fully censored rather than left
        # clear by a degenerate ellipse PIL won't render.
        mask.paste(255, (0, 0, w, h))
        return mask
    ImageDraw.Draw(mask).ellipse((margin_x, margin_y, x2, y2), fill=255)
    return mask


def _region_mask(w, h, shape, seg_mask=None):
    """Compositing mask for the region, or ``None`` for a full-rectangle paste.

    RECT → None (paste the whole box). ELLIPSE → inscribed ellipse. PRECISE →
    the supplied per-region segmentation mask, falling back to an ellipse when
    no mask is available (segmentation model absent / failed).
    """
    if shape == SHAPE_ELLIPSE:
        return _ellipse_mask(w, h)
    if shape == SHAPE_PRECISE:
        return seg_mask if seg_mask is not None else _ellipse_mask(w, h)
    return None  # SHAPE_RECT


def _censor_region(img, x1, y1, x2, y2, block_size, *, style=STYLE_MOSAIC,
                   shape=SHAPE_RECT, seg_mask=None):
    """Censor a region in-place, confined to *shape*.

    The censored pixels are produced for the whole box, then composited back
    through the shape mask so only the ellipse / segmentation area is replaced
    and the rectangular corners keep their original pixels.
    """
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return
    box = (x1, y1, x2, y2)
    region = img.crop(box)
    censored = _censored_region(region, w, h, block_size, style)
    img.paste(censored, (x1, y1), _region_mask(w, h, shape, seg_mask))


def _shrink_box_center(box, frac: float):
    """Central sub-box of *box* scaled to *frac* of each side."""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    hw, hh = (x2 - x1) * frac / 2, (y2 - y1) * frac / 2
    return (int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh))


def _ensure_parent(dst: str) -> None:
    """Create *dst*'s parent directory on demand, right before a write.

    Destination helpers only compute paths; the mirrored output tree is
    materialised here so a run that skips clean images (only-censored mode)
    never leaves empty subfolders behind.
    """
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _boxes_touch(a, b, gap: int) -> bool:
    """True when box *a* grown by *gap* px reaches box *b*."""
    return (a[0] - gap <= b[2] and b[0] <= a[2] + gap
            and a[1] - gap <= b[3] and b[1] <= a[3] + gap)


def _boxes_overlap(a, b) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _merge_gap(boxes) -> int:
    """Gap threshold for bridging, scaled to the boxes' median short edge."""
    edges = [min(x2 - x1, y2 - y1) for x1, y1, x2, y2 in boxes]
    if not edges:
        return 0
    median = sorted(edges)[len(edges) // 2]
    return int(median * _MERGE_GAP_FRAC)


def _bridge_box(a, b):
    """Minimal rectangle that covers the gap between two nearby boxes.

    For side-by-side boxes it spans the x-gap over only their overlapping y
    band (and vice-versa), so the junction seam is covered without the empty
    corners a full bounding-box union would add. Falls back to the bounding
    box when the boxes don't share a band on either axis.
    """
    ux = (min(a[0], b[0]), max(a[2], b[2]))
    uy = (min(a[1], b[1]), max(a[3], b[3]))
    x_band = (max(a[0], b[0]), min(a[2], b[2]))
    y_band = (max(a[1], b[1]), min(a[3], b[3]))
    if y_band[0] < y_band[1]:            # share a horizontal band → x-gap bridge
        return (ux[0], y_band[0], ux[1], y_band[1])
    if x_band[0] < x_band[1]:            # share a vertical band → y-gap bridge
        return (x_band[0], uy[0], x_band[1], uy[1])
    return (ux[0], uy[0], ux[1], uy[1])  # diagonal → bounding box


def _junction_bridges(boxes, gap: int):
    """Bridge rectangles for each near-but-separate pair of boxes.

    A penetration junction sits in the gap between the two genital boxes;
    bridging only that gap covers the seam while keeping each censor tight —
    no runaway bounding-box union that swallows the area around a chain of
    detections.
    """
    bridges = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if _boxes_touch(a, b, gap) and not _boxes_overlap(a, b):
                bridges.append(_bridge_box(a, b))
    return bridges
