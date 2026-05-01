"""Auto colour-separation — split a flatted layer into one per colour.

The classic comic-colourist workflow leaves a single layer of flat
colour blocks (the bucket-fill output) that the artist later wants to
shade. Shading a single mixed-colour layer is awkward — every brush
stroke risks bleeding past a colour boundary. MediBang exposes a
"Divide Layer" command that walks the flat layer, gathers the
distinct colours, and produces a layer per colour with each painted
only where that colour was. Shading then targets one layer at a time.

This module is the pure-numpy logic. It does NOT touch the
:class:`Imervue.paint.document.PaintDocument` directly — the document
verb in :mod:`Imervue.paint.document` consumes
:func:`divide_layer_into_color_layers` and rebuilds the stack.

A naive "every distinct RGB tuple = its own layer" strategy explodes
on anti-aliased boundaries. The implementation quantises each pixel
to a configurable bucket size and groups the original colours that
fall into the same bucket. The output uses the dominant (most-pixel)
original colour from each bucket so the resulting layers still match
what the artist sees.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# A raw flat-fill canvas can have hundreds of unique colours after
# anti-aliased blends; clamping at this many buckets keeps the result
# tractable for the layer dock and avoids OOM on a corner-case input.
MAX_DIVIDE_BUCKETS = 64

# Bucket size in 0..255 RGB space. 16 means "round each channel to
# the nearest 16" — gives 16^3 = 4096 buckets in the worst case but
# typical flat-fill input collapses to a handful of buckets.
DEFAULT_QUANTIZE = 16
QUANTIZE_MIN = 1
QUANTIZE_MAX = 64


@dataclass(frozen=True)
class ColorLayer:
    """One discovered flat colour plus the mask of pixels matching it."""

    color: tuple[int, int, int]
    mask: np.ndarray   # HxW bool — True where this colour was found
    pixel_count: int   # cached so callers can sort by area


def divide_layer_into_color_layers(
    image: np.ndarray,
    *,
    quantize: int = DEFAULT_QUANTIZE,
    max_buckets: int = MAX_DIVIDE_BUCKETS,
    alpha_threshold: int = 128,
) -> list[ColorLayer]:
    """Split a flat-colour layer into one mask per distinct colour.

    Pixels whose alpha is at or below ``alpha_threshold`` are treated
    as background and never contribute a mask of their own. The result
    is sorted by ``pixel_count`` descending so the dominant colour
    (typically the largest flat region) is layer 0.

    Returns at most ``max_buckets`` :class:`ColorLayer`. With more
    distinct colours than that, the smallest buckets are dropped —
    they are statistically the artefacts at colour boundaries that
    the artist did not intend as separate fills.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got shape={image.shape}"
            f" dtype={image.dtype}",
        )
    quantize = _validate_quantize(quantize)
    if max_buckets <= 0:
        raise ValueError(f"max_buckets must be > 0, got {max_buckets}")
    if not 0 <= int(alpha_threshold) <= 255:
        raise ValueError(
            f"alpha_threshold must be in [0, 255], got {alpha_threshold}",
        )

    rgb = image[..., :3]
    alpha = image[..., 3]
    opaque = alpha > int(alpha_threshold)
    if not opaque.any():
        return []

    # Quantised key per pixel — encoded as a single int so we can
    # group by it efficiently. ``quantize`` rounds each channel down
    # to a multiple; the encoded key only fits in 24 bits.
    quantized = (rgb // quantize) * quantize
    keys = (
        quantized[..., 0].astype(np.uint32) << 16
        | quantized[..., 1].astype(np.uint32) << 8
        | quantized[..., 2].astype(np.uint32)
    )

    # Tally counts per key, restricted to opaque pixels.
    masked_keys = keys[opaque]
    masked_rgb = rgb[opaque]
    unique_keys, counts = np.unique(masked_keys, return_counts=True)

    layers: list[ColorLayer] = []
    for key, count in zip(unique_keys, counts, strict=True):
        bucket_mask = (keys == key) & opaque
        if not bucket_mask.any():
            continue
        # Pick the representative colour as the median of the
        # original colours in this bucket — robust to a handful of
        # off-axis aliased pixels and stays inside the bucket span.
        bucket_pixels = masked_rgb[masked_keys == key]
        rep = np.median(bucket_pixels, axis=0).astype(np.uint8)
        layers.append(ColorLayer(
            color=(int(rep[0]), int(rep[1]), int(rep[2])),
            mask=bucket_mask,
            pixel_count=int(count),
        ))

    layers.sort(key=lambda layer: layer.pixel_count, reverse=True)
    return layers[:max_buckets]


def render_color_layer(
    shape: tuple[int, int], color_layer: ColorLayer,
) -> np.ndarray:
    """Build the HxWx4 RGBA image for one discovered colour.

    The mask becomes the alpha (255 inside / 0 outside) and the
    representative colour fills the RGB channels. ``shape`` is
    ``(height, width)``.
    """
    h, w = shape
    if color_layer.mask.shape != (h, w):
        raise ValueError(
            f"mask shape {color_layer.mask.shape} does not match "
            f"requested shape {(h, w)}",
        )
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[color_layer.mask, 0] = color_layer.color[0]
    out[color_layer.mask, 1] = color_layer.color[1]
    out[color_layer.mask, 2] = color_layer.color[2]
    out[color_layer.mask, 3] = 255
    return out


def _validate_quantize(quantize: int) -> int:
    try:
        value = int(quantize)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"quantize must be an integer, got {quantize!r}",
        ) from exc
    if value < QUANTIZE_MIN:
        raise ValueError(f"quantize must be >= {QUANTIZE_MIN}, got {value}")
    if value > QUANTIZE_MAX:
        raise ValueError(f"quantize must be <= {QUANTIZE_MAX}, got {value}")
    return value
