"""Halftone screentone engine — value-mapped + masked dot/line tones.

Phase 23a already shipped tileable dot / line / gradient primitives.
This module is the next layer up: it converts a per-pixel **value**
(luminance, alpha, or any user-supplied 0..1 mask) into a per-pixel
**tone density** so the artist can paint mid-tones with greys and
have them automatically rendered as the correct halftone density.

Why bother
----------

MediBang (and Clip Studio) expose this as the "Tone Curve" feature:
you paint with grey, hit the convert button, and your soft grey
shading turns into a sharp black-and-white dot pattern that prints
cleanly on cheap manga paper. That is what
:func:`apply_halftone_to_alpha` and :func:`map_value_to_halftone` do
here, in pure numpy. Tile generation itself stays in
:mod:`Imervue.paint.material_procedural` so the dock keeps using
those for thumbnails.

The functions all operate on ``HxW`` value arrays (``float32`` in
``[0, 1]``) or ``HxWx4`` ``uint8`` RGBA layers, and return new
arrays — they never mutate the input.
"""
from __future__ import annotations

import math

import numpy as np

# Density of dots / lines is tied to the per-pixel value through a
# global "lpi" (lines per inch) parameter — same convention as
# Photoshop / MediBang. The range below covers the practical print
# range (10 LPI = chunky tone, 85 LPI = magazine grade). A canvas-
# space conversion happens inside the renderer (lpi → cell pixels).
HALFTONE_LPI_MIN = 10
HALFTONE_LPI_MAX = 200
DEFAULT_LPI = 60

# Dot density never goes below 5% or above 95% — pure black / pure
# white is rendered as a flat fill instead of a dot grid because the
# grid is invisible at the extremes anyway.
_MIN_DENSITY = 0.05
_MAX_DENSITY = 0.95


def value_to_density(value: np.ndarray) -> np.ndarray:
    """Map a 0..1 value field into a 0..1 dot-coverage field.

    Linear in the middle, clamped at the endpoints so the rendered
    tone never collapses to all-black or all-white (those produce a
    flat fill rather than a dot pattern). Input is treated as
    luminance — high value → light → fewer dots.

    Returns a fresh ``float32`` array with the same shape as ``value``.
    """
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(
            f"value_to_density expects a 2-D array, got shape={arr.shape}",
        )
    clipped = np.clip(arr, 0.0, 1.0)
    # Higher value → lighter region → fewer dots, so density = 1 - value.
    density = 1.0 - clipped
    return np.clip(density, _MIN_DENSITY, _MAX_DENSITY).astype(np.float32)


def lpi_to_cell_pixels(lpi: int, *, dpi: int = 300) -> int:
    """Convert lines-per-inch into the per-cell pixel size at ``dpi``.

    Caller picks ``dpi`` to match the export target (300 DPI for
    print, 72 for screen previews). Result is clamped to a minimum
    of 2 px so anti-aliasing has somewhere to live.
    """
    if lpi <= 0:
        raise ValueError(f"lpi must be positive, got {lpi}")
    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi}")
    return max(2, int(round(dpi / lpi)))


def render_halftone_dots(
    density: np.ndarray, *, cell: int,
) -> np.ndarray:
    """Rasterise a density field into a black-on-transparent dot tile.

    For each ``cell``-sized square, pick a dot radius proportional to
    ``sqrt(density)`` so the *area* of the dot scales linearly with
    the density (matching the optical perception of tone strength).
    The output covers the full extent of ``density`` and is RGBA with
    only the alpha channel populated.
    """
    arr = np.asarray(density, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(
            f"density must be a 2-D array, got shape={arr.shape}",
        )
    if cell < 2:
        raise ValueError(f"cell must be >= 2, got {cell}")
    h, w = arr.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    half = cell / 2.0
    yy, xx = np.indices((h, w))
    cy = (yy // cell) * cell + half - 0.5
    cx = (xx // cell) * cell + half - 0.5
    dy = yy - cy
    dx = xx - cx
    dist_sq = dx * dx + dy * dy
    # Per-cell density: pull from the cell's centre pixel so a single
    # density value drives the whole dot rather than per-pixel jitter.
    cell_density = arr[
        np.clip(cy.astype(np.int32), 0, h - 1),
        np.clip(cx.astype(np.int32), 0, w - 1),
    ]
    # Radius proportional to sqrt(density) keeps optical tone linear.
    radius = half * np.sqrt(np.clip(cell_density, 0.0, 1.0))
    inside = dist_sq <= (radius * radius)
    out[..., 3] = (inside * 255).astype(np.uint8)
    return out


def apply_halftone_to_alpha(
    layer: np.ndarray, *, lpi: int = DEFAULT_LPI, dpi: int = 300,
) -> np.ndarray:
    """Convert a soft greyscale-painted layer into a sharp dot tone.

    Reads the per-pixel **alpha** as the density source — this is the
    typical "I painted with a soft black brush, now turn it into a
    dot pattern" workflow. The colour channels are forced to black
    (the standard manga screentone colour); a future option could
    keep the original colour but the printed-manga convention is
    pure black ink.

    Returns a new HxWx4 uint8 RGBA layer; the input is unchanged.
    """
    if layer.ndim != 3 or layer.shape[2] != 4 or layer.dtype != np.uint8:
        raise ValueError(
            f"layer must be HxWx4 uint8 RGBA, got shape={layer.shape}"
            f" dtype={layer.dtype}",
        )
    cell = lpi_to_cell_pixels(lpi, dpi=dpi)
    value = layer[..., 3].astype(np.float32) / 255.0
    # Treat alpha as "ink amount" — high alpha == dark area == many dots.
    density = np.clip(value, _MIN_DENSITY, _MAX_DENSITY).astype(np.float32)
    dots = render_halftone_dots(density, cell=cell)
    return dots


def apply_halftone_to_image(
    layer: np.ndarray, *, lpi: int = DEFAULT_LPI, dpi: int = 300,
) -> np.ndarray:
    """Convert any RGBA layer (paint or photo) into a black halftone.

    Density source = ``(1 - luminance) * alpha`` — so the conversion
    behaves correctly across the two common workflows:

    * **Soft-brushed shading on a transparent layer** — luminance is
      near-black for painted regions, alpha varies with brush opacity,
      so the density tracks where the artist actually laid ink down.
    * **Imported greyscale photo** — alpha is 255 across the layer,
      so density tracks ``1 - luminance`` directly. A black
      background renders as solid dots; a white background as none.

    Returns a new HxWx4 uint8 RGBA layer of black-on-transparent dots.
    """
    if layer.ndim != 3 or layer.shape[2] != 4 or layer.dtype != np.uint8:
        raise ValueError(
            f"layer must be HxWx4 uint8 RGBA, got shape={layer.shape}"
            f" dtype={layer.dtype}",
        )
    rgb = layer[..., :3].astype(np.float32) / 255.0
    # Rec. 709 luminance — same coefficients used elsewhere in the project.
    luma = (
        0.2126 * rgb[..., 0]
        + 0.7152 * rgb[..., 1]
        + 0.0722 * rgb[..., 2]
    )
    alpha = layer[..., 3].astype(np.float32) / 255.0
    density = np.clip((1.0 - luma) * alpha, _MIN_DENSITY, _MAX_DENSITY)
    cell = lpi_to_cell_pixels(lpi, dpi=dpi)
    return render_halftone_dots(density.astype(np.float32), cell=cell)


def map_value_to_halftone(
    value: np.ndarray,
    *,
    color: tuple[int, int, int] = (0, 0, 0),
    lpi: int = DEFAULT_LPI,
    dpi: int = 300,
) -> np.ndarray:
    """Render a free-form value field as a coloured halftone layer.

    Mirrors :func:`apply_halftone_to_alpha` but takes the value field
    as a separate 0..1 array (luminance, mask, anything the caller
    has computed) and ``color`` as the ink colour. Used by the
    "Convert to halftone" command in the manga menu when the source
    is a luminance map rather than a soft paint layer.
    """
    if not (0 <= color[0] <= 255 and 0 <= color[1] <= 255 and 0 <= color[2] <= 255):
        raise ValueError(
            f"color components must be in 0..255, got {color}",
        )
    cell = lpi_to_cell_pixels(lpi, dpi=dpi)
    density = value_to_density(np.asarray(value, dtype=np.float32))
    dots = render_halftone_dots(density, cell=cell)
    out = dots.copy()
    out[..., 0] = color[0]
    out[..., 1] = color[1]
    out[..., 2] = color[2]
    # Preserve the dot alpha generated above.
    return out


def rotate_tile(tile: np.ndarray, *, angle_deg: float) -> np.ndarray:
    """Rotate a tile around its centre, with same-size output.

    Pixels that fall off the rotated tile become fully transparent.
    The rotation is nearest-neighbour to keep the dot edges crisp —
    bilinear would soften the halftone and lose its identity.
    """
    if tile.ndim != 3 or tile.shape[2] != 4 or tile.dtype != np.uint8:
        raise ValueError(
            f"tile must be HxWx4 uint8 RGBA, got shape={tile.shape}"
            f" dtype={tile.dtype}",
        )
    if angle_deg % 360 == 0:
        return tile.copy()
    h, w = tile.shape[:2]
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    yy, xx = np.indices((h, w)).astype(np.float32)
    # Inverse map: where in the source did each output pixel come from?
    src_x = cos_a * (xx - cx) + sin_a * (yy - cy) + cx
    src_y = -sin_a * (xx - cx) + cos_a * (yy - cy) + cy
    sx = np.round(src_x).astype(np.int32)
    sy = np.round(src_y).astype(np.int32)
    valid = (sx >= 0) & (sx < w) & (sy >= 0) & (sy < h)
    out = np.zeros_like(tile)
    out[valid] = tile[sy[valid], sx[valid]]
    return out
