"""Auto base-color fill — flat-colour every closed region of a lineart.

The colourist's setup phase: take a lineart (typically on its own
layer, with ink either drawn opaque on transparent or as dark luma
on a white background), find every closed region the lines enclose,
and pre-fill each with a different flat colour. The output is one
RGBA mask per region so the caller can either splat them all into a
single new layer or spread them across many layers.

The algorithm:

1. Compute an *ink mask* from the reference image (alpha-based or
   luma-based — same source semantics as
   :class:`Imervue.paint.binary_layer.BinarySettings`).
2. Optionally dilate the ink to close small gaps in the linework
   (same MediBang "Color Drop" trick exposed in 28a).
3. Walk the non-ink pixels and run a 4-connected flood from every
   unvisited cell. Each flood produces one region mask.
4. Drop regions smaller than ``min_region_size`` (anti-aliased
   speckles that would otherwise spam the output).
5. Assign each surviving region a colour — palette-cycled or
   procedural HSV-rotation — and return the list sorted by area.
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass

import numpy as np

# Caps to keep an adversarial reference (a noisy photo with no real
# closed regions) from spamming the layer dock.
MAX_REGIONS = 256
DEFAULT_MIN_REGION_SIZE = 32


@dataclass(frozen=True)
class BaseColorRegion:
    """One filled region — colour + boolean mask + pixel count."""

    color: tuple[int, int, int]
    mask: np.ndarray   # HxW bool — True where the region was found
    pixel_count: int


def auto_base_fill(
    reference: np.ndarray,
    *,
    palette: list[tuple[int, int, int]] | None = None,
    ink_alpha_threshold: int = 64,
    gap_close: int = 0,
    min_region_size: int = DEFAULT_MIN_REGION_SIZE,
    max_regions: int = MAX_REGIONS,
    seed: int = 0,
) -> list[BaseColorRegion]:
    """Return one :class:`BaseColorRegion` per detected closed region.

    ``reference`` is the lineart — HxWx4 uint8 RGBA. Pixels with
    alpha greater than ``ink_alpha_threshold`` count as ink (the
    standard MediBang line-on-transparent convention). When the
    lineart is drawn dark on white instead, callers can use
    :func:`apply_white_background_to_alpha` first or pre-threshold
    the reference themselves.

    ``gap_close`` (>= 0) dilates the ink by that many 4-connected
    pixels before region-finding so small breaks in the lineart
    don't merge two separate regions into one.

    Regions smaller than ``min_region_size`` pixels are dropped so
    AA speckles around the ink don't yield 1-pixel "regions". The
    output is sorted by area descending and capped at
    ``max_regions``; callers wanting more should bump the cap.
    """
    if reference.ndim != 3 or reference.shape[2] != 4 or reference.dtype != np.uint8:
        raise ValueError(
            f"reference must be HxWx4 uint8 RGBA, got shape={reference.shape}"
            f" dtype={reference.dtype}",
        )
    if not 0 <= int(ink_alpha_threshold) <= 255:
        raise ValueError(
            f"ink_alpha_threshold must be in [0, 255], got {ink_alpha_threshold}",
        )
    if int(min_region_size) < 1:
        raise ValueError(
            f"min_region_size must be >= 1, got {min_region_size}",
        )
    if int(max_regions) < 1:
        raise ValueError(f"max_regions must be >= 1, got {max_regions}")

    h, w = reference.shape[:2]
    ink = reference[..., 3] > int(ink_alpha_threshold)
    if int(gap_close) > 0:
        from Imervue.paint.selection_ops import expand as dilate
        ink = dilate(ink, int(gap_close))
    open_pixels = ~ink

    visited = np.zeros((h, w), dtype=np.bool_)
    regions: list[BaseColorRegion] = []
    palette_list = _materialise_palette(palette, seed=int(seed))

    from Imervue.paint.fill import _contiguous_region

    for sy in range(h):
        for sx in range(w):
            if visited[sy, sx] or ink[sy, sx]:
                continue
            mask = _contiguous_region(open_pixels, sx, sy)
            count = int(mask.sum())
            if count == 0:
                visited[sy, sx] = True
                continue
            visited |= mask
            if count < int(min_region_size):
                continue
            color = palette_list[len(regions) % len(palette_list)]
            regions.append(BaseColorRegion(
                color=color, mask=mask, pixel_count=count,
            ))
            if len(regions) >= int(max_regions):
                # Mark every remaining open pixel as visited so the
                # outer scan exits early without re-flooding.
                visited |= open_pixels & ~visited
                break
        else:
            continue
        break

    regions.sort(key=lambda r: r.pixel_count, reverse=True)
    return regions


def _materialise_palette(
    palette: list[tuple[int, int, int]] | None,
    *,
    seed: int,
) -> list[tuple[int, int, int]]:
    """Either pass through ``palette`` or generate a default one.

    The default palette is a 12-colour HSV ring at fixed saturation /
    value so the auto-fill output reads as discrete "flat colours"
    rather than a noisy random spread. The seed shifts the starting
    hue so successive runs on the same image don't always pick the
    same first colour.
    """
    if palette:
        if any(len(c) != 3 or any(not 0 <= int(x) <= 255 for x in c) for c in palette):
            raise ValueError(
                "palette colours must be 3-tuples of 0..255 ints",
            )
        return [tuple(int(x) for x in c) for c in palette]
    # Default: 12-stop HSV ring.
    n = 12
    hue_offset = (seed % 360) / 360.0
    saturation = 0.6
    value = 0.95
    out: list[tuple[int, int, int]] = []
    for i in range(n):
        hue = (hue_offset + i / n) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        out.append((
            int(round(r * 255)),
            int(round(g * 255)),
            int(round(b * 255)),
        ))
    return out


def regions_to_layer_image(
    canvas_shape: tuple[int, int],
    regions: list[BaseColorRegion],
) -> np.ndarray:
    """Splat every region's colour into one fresh HxWx4 RGBA buffer.

    Convenience for callers that want a single base-colour layer —
    each region's mask paints its colour at full alpha; pixels not
    covered by any region stay transparent.
    """
    h, w = canvas_shape
    if h <= 0 or w <= 0:
        raise ValueError(
            f"canvas_shape must be positive, got {canvas_shape!r}",
        )
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for region in regions:
        if region.mask.shape != (h, w):
            raise ValueError(
                f"region mask {region.mask.shape} does not match "
                f"canvas {(h, w)}",
            )
        out[region.mask, 0] = region.color[0]
        out[region.mask, 1] = region.color[1]
        out[region.mask, 2] = region.color[2]
        out[region.mask, 3] = 255
    return out
