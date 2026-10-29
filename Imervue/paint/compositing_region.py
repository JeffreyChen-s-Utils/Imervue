"""Dirty-rect compositing: recomposite just one rectangle of the stack.

Used by :class:`Imervue.paint.document_composite` to patch a cached
full-frame composite after a brush stroke. Only per-pixel layer
transforms can be sliced; a stack holding a layer effect or an
adjustment layer makes :func:`composite_region` return ``None`` so the
caller falls back to the full :func:`Imervue.paint.compositing.composite_stack`.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from Imervue.paint.compositing_layer import (
    _apply_clip,
    _layer_image_with_tone,
    _realise_vector_cache,
    _resolve_group_opacity,
)
from Imervue.paint.compositing_pair import composite_layer_pair


def _layer_supports_region_composite(layer) -> bool:
    """Return True iff a sliced recomposite produces correct pixels.

    Layer effects (drop shadow / outer glow / stroke) and adjustment
    layers depend on context outside the dirty rect — a glow leaks
    past the layer bounds, an adjustment reads the full background.
    Per-pixel transforms (mask, blend mode, opacity, tone, binary,
    blend_if) are safe because they operate independently per pixel.
    """
    if getattr(layer, "effects", ()):
        return False
    return getattr(layer, "adjustment", None) is None


def composite_region(
    layers: Iterable,
    base_shape: tuple[int, int],
    rect: tuple[int, int, int, int],
    groups: dict | None = None,
) -> np.ndarray | None:
    """Composite just ``rect`` of the layer stack, or return ``None``.

    ``rect`` is ``(x, y, w, h)`` in image-space pixels, already clipped
    to ``base_shape``. The result is an HxWx4 RGBA buffer of size
    ``(rect.h, rect.w, 4)`` — exactly the slice the caller can paste
    into its cached full-frame composite.

    Returns ``None`` if any layer in the stack uses an effect or
    adjustment that depends on out-of-rect context; the caller is
    expected to fall back to :func:`composite_stack` in that case.
    """
    layer_list = list(layers)
    if not layer_list:
        h, w = base_shape
        return np.zeros((h, w, 4), dtype=np.uint8)
    if not all(_layer_supports_region_composite(layer) for layer in layer_list):
        return None
    if not _rect_fits_inside(rect, base_shape):
        return None
    if any(layer.image.shape[:2] != base_shape for layer in layer_list):
        return None

    groups = groups or {}
    _, _, rw, rh = rect
    out = np.zeros((rh, rw, 4), dtype=np.uint8)
    clip_base_alpha: np.ndarray | None = None
    for layer in layer_list:
        out, clip_base_alpha = _composite_region_layer(
            out, layer, rect, clip_base_alpha, groups,
        )
    return out


def _rect_fits_inside(
    rect: tuple[int, int, int, int], base_shape: tuple[int, int],
) -> bool:
    x, y, rw, rh = rect
    h, w = base_shape
    return rw > 0 and rh > 0 and x >= 0 and y >= 0 and x + rw <= w and y + rh <= h


def _composite_region_layer(
    out: np.ndarray, layer, rect: tuple[int, int, int, int],
    clip_base_alpha: np.ndarray | None, groups: dict,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Composite a single layer's slice onto ``out`` and return the
    next ``(out, clip_base_alpha)`` pair. Skipping any layer that
    isn't visible (group hidden / zero opacity) is a transparent
    pass-through — clip-base tracking still updates because the
    underlying pixels could still anchor a clipping layer above."""
    group_opacity = _resolve_group_opacity(layer, groups)
    if group_opacity is None:
        return out, clip_base_alpha
    if not layer.visible or layer.opacity <= 0:
        return out, clip_base_alpha

    _realise_vector_cache(layer)
    layer_image = _layer_image_with_tone(layer)

    x, y, rw, rh = rect
    layer_slice = layer_image[y:y + rh, x:x + rw]
    sliced_mask = _resolve_region_mask(
        layer, clip_base_alpha, layer_slice, out, rect,
    )
    out = composite_layer_pair(
        out, layer_slice,
        opacity=layer.opacity * group_opacity,
        blend_mode=layer.blend_mode,
        mask=sliced_mask,
    )
    if not getattr(layer, "clip", False):
        # ``clip_base_alpha`` is queried full-frame by the next
        # clipping layer's ``_apply_clip``; keep it at the document
        # size so the slice arithmetic above stays correct.
        clip_base_alpha = layer.image[..., 3].copy()
    return out, clip_base_alpha


def _resolve_region_mask(
    layer, clip_base_alpha: np.ndarray | None,
    layer_slice: np.ndarray, out: np.ndarray,
    rect: tuple[int, int, int, int],
) -> np.ndarray | None:
    """Combine the layer's effective_mask, clip-mask, and any
    blend_if alpha into a single uint8 mask sliced to ``rect``."""
    x, y, rw, rh = rect
    full_mask = _apply_clip(
        layer, getattr(layer, "effective_mask", layer.mask), clip_base_alpha,
    )
    sliced_mask = (
        None if full_mask is None else full_mask[y:y + rh, x:x + rw]
    )
    blend_if = getattr(layer, "blend_if", None)
    if blend_if is None:
        return sliced_mask
    from Imervue.paint.blend_if import compute_blend_if_mask
    blend_alpha = compute_blend_if_mask(layer_slice, out, blend_if)
    if sliced_mask is None:
        return (blend_alpha * 255.0).clip(0, 255).astype(np.uint8)
    combined = (sliced_mask.astype(np.float32) / 255.0) * blend_alpha
    return (combined * 255.0).clip(0, 255).astype(np.uint8)

