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
   (same raster paint apps "Color Drop" trick exposed in 28a).
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
    exclude_border: bool = False,
) -> list[BaseColorRegion]:
    """Return one :class:`BaseColorRegion` per detected closed region.

    ``reference`` is the lineart — HxWx4 uint8 RGBA. Pixels with
    alpha greater than ``ink_alpha_threshold`` count as ink (the
    standard raster paint apps line-on-transparent convention). When the
    lineart is drawn dark on white instead, callers can use
    :func:`apply_white_background_to_alpha` first or pre-threshold
    the reference themselves.

    ``gap_close`` (>= 0) dilates the ink by that many 4-connected
    pixels before region-finding so small breaks in the lineart
    don't merge two separate regions into one.

    Regions smaller than ``min_region_size`` pixels are dropped so
    AA speckles around the ink don't yield 1-pixel "regions"; with
    ``exclude_border`` so are regions touching the image edge — the space
    around the drawing rather than a shape in it. The output is sorted by
    area descending and capped at ``max_regions``; callers wanting more
    should bump the cap.
    """
    _validate_auto_base_args(
        reference, ink_alpha_threshold, min_region_size, max_regions,
    )
    open_pixels = _open_pixels_after_gap_close(
        reference, ink_alpha_threshold, gap_close,
    )
    palette_list = _materialise_palette(palette, seed=int(seed))
    regions = _scan_open_regions(
        open_pixels, palette_list,
        min_region_size=int(min_region_size),
        max_regions=int(max_regions),
        exclude_border=bool(exclude_border),
    )
    regions.sort(key=lambda r: r.pixel_count, reverse=True)
    return regions


def _validate_auto_base_args(
    reference: np.ndarray, ink_alpha_threshold: int,
    min_region_size: int, max_regions: int,
) -> None:
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


def _open_pixels_after_gap_close(
    reference: np.ndarray, ink_alpha_threshold: int, gap_close: int,
) -> np.ndarray:
    ink = reference[..., 3] > int(ink_alpha_threshold)
    if int(gap_close) > 0:
        from Imervue.paint.selection_ops import expand as dilate
        ink = dilate(ink, int(gap_close))
    return ~ink


def _scan_open_regions(
    open_pixels: np.ndarray, palette_list: list[tuple[int, int, int]],
    *, min_region_size: int, max_regions: int, exclude_border: bool,
) -> list[BaseColorRegion]:
    """One region per 4-connected group of open pixels, in raster order of first appearance.

    Groups smaller than *min_region_size*, and with *exclude_border* those
    touching the image edge (the space around the drawing), are skipped; the
    palette cycles over the kept ones. At most *max_regions* are returned;
    the caller sorts them by ``pixel_count``.
    """
    labels = _kept_labels(open_pixels, min_region_size=min_region_size,
                          exclude_border=exclude_border)
    grid = labels[0]
    regions: list[BaseColorRegion] = []
    for index, (label, count) in enumerate(labels[1][:max_regions]):
        color = palette_list[index % len(palette_list)]
        regions.append(BaseColorRegion(color=color, mask=grid == label, pixel_count=count))
    return regions


def _kept_labels(
    open_pixels: np.ndarray, *, min_region_size: int, exclude_border: bool,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """The label grid and ``(label, pixel count)`` of each region worth keeping, in raster order."""
    grid, count = label_open_regions(open_pixels)
    sizes = np.bincount(grid.ravel(), minlength=count + 1)
    dropped = np.zeros(count + 1, dtype=np.bool_)
    dropped[0] = True
    dropped[sizes < int(min_region_size)] = True
    if exclude_border:
        edge = np.concatenate((grid[0], grid[-1], grid[:, 0], grid[:, -1]))
        dropped[np.unique(edge)] = True
    kept = [(int(label), int(sizes[label])) for label in np.nonzero(~dropped)[0]]
    return grid, kept


def label_open_regions(open_pixels: np.ndarray) -> tuple[np.ndarray, int]:
    """Label the 4-connected groups of ``True`` cells: an int32 grid (0 = closed) and the count.

    Labels run 1..count in raster order of each group's first cell. Each row's
    runs come from numpy and are joined to the overlapping runs of the row
    above with a union-find, so the Python work follows the number of runs,
    not of pixels (an A4 page at 300 dpi takes well under a second).
    """
    h, w = open_pixels.shape
    parent: list[int] = [0]
    runs: list[tuple[int, int, int, int]] = []          # (row, first col, last col, label)
    above: list[tuple[int, int, int]] = []
    for y in range(h):
        above = _label_row(open_pixels[y], y, above, parent, runs)
    roots = [_find(parent, label) for label in range(len(parent))]
    compact = np.zeros(len(parent), dtype=np.int32)
    order: dict[int, int] = {}
    for label in range(1, len(parent)):
        root = roots[label]
        if root not in order:
            order[root] = len(order) + 1
        compact[label] = order[root]
    grid = np.zeros((h, w), dtype=np.int32)
    for y, x0, x1, label in runs:
        grid[y, x0:x1 + 1] = compact[label]
    return grid, len(order)


def _label_row(
    row: np.ndarray, y: int, above: list[tuple[int, int, int]], parent: list[int],
    runs: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int]]:
    """Label row *y*'s runs, joining each to the runs above it that it touches."""
    edges = np.diff(np.concatenate(([False], row, [False])).astype(np.int8))
    starts = np.nonzero(edges == 1)[0].tolist()
    ends = (np.nonzero(edges == -1)[0] - 1).tolist()
    current: list[tuple[int, int, int]] = []
    first = 0
    for x0, x1 in zip(starts, ends, strict=True):
        while first < len(above) and above[first][1] < x0:
            first += 1                        # runs above that end before this one starts
        label = 0
        k = first
        while k < len(above) and above[k][0] <= x1:
            label = _union(parent, label, above[k][2])
            k += 1
        if label == 0:
            label = len(parent)
            parent.append(label)
        current.append((x0, x1, label))
        runs.append((y, x0, x1, label))
    return current


def _find(parent: list[int], label: int) -> int:
    while parent[label] != label:
        parent[label] = parent[parent[label]]
        label = parent[label]
    return label


def _union(parent: list[int], a: int, b: int) -> int:
    """Join the groups of labels *a* (0 = none yet) and *b*; return the surviving root."""
    rb = _find(parent, b)
    if a == 0:
        return rb
    ra = _find(parent, a)
    if ra == rb:
        return ra
    low, high = min(ra, rb), max(ra, rb)
    parent[high] = low
    return low


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


def base_colour_layer(
    lineart: np.ndarray,
    *,
    palette: list[tuple[int, int, int]] | None = None,
    gap_close: int = 0,
    min_region_size: int = DEFAULT_MIN_REGION_SIZE,
    max_regions: int = MAX_REGIONS,
) -> tuple[np.ndarray, int]:
    """The flat-colour layer under *lineart*, and how many regions it fills.

    Every closed region gets its own colour (cycling *palette*, else the
    default ring); the space around the drawing and the lines stay
    transparent. Opaque line art (dark lines on white) is read by darkness,
    transparent line art by its alpha. Built from one label grid and a colour
    lookup, without a mask per region, so it suits a full page.
    """
    reference = lineart_ink(lineart)
    _validate_auto_base_args(reference, 64, min_region_size, max_regions)
    open_pixels = _open_pixels_after_gap_close(reference, 64, gap_close)
    grid, kept = _kept_labels(open_pixels, min_region_size=min_region_size,
                              exclude_border=True)
    kept = kept[:max_regions]
    colours = _materialise_palette(palette, seed=0)
    lut = np.zeros((int(grid.max()) + 1, 4), dtype=np.uint8)
    for index, (label, _count) in enumerate(kept):
        lut[label] = (*colours[index % len(colours)], 255)
    return lut[grid], len(kept)


def lineart_ink(image: np.ndarray) -> np.ndarray:
    """*image* with its alpha saying where the ink is.

    Line art drawn on transparency already does; a fully opaque layer (dark
    lines on white paper) gets an alpha that grows with darkness, so its
    lines count as ink and its paper as open space.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}")
    if int(image[..., 3].min()) < 255:
        return image
    luma = (image[..., 0] * 0.299 + image[..., 1] * 0.587 + image[..., 2] * 0.114)
    out = image.copy()
    out[..., 3] = (255 - luma).astype(np.uint8)
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
