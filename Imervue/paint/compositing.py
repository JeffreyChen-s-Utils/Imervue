"""Pure-numpy layer compositing for the Paint workspace.

The brush engine's dab compositing handles the "paint a single colour
through an alpha kernel" case. Layer compositing is a different
operation — taking two HxWx4 RGBA buffers (each with its own alpha
channel) and combining them through one of the 12 blend modes that
the rest of Imervue supports.

Used by :class:`Imervue.paint.document.PaintDocument` to flatten the
layer stack into a single RGBA buffer that the GL canvas uploads as a
texture.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from Imervue.paint.compositing_layer import (
    _apply_adjustment_layer,
    _apply_clip,
    _layer_image_with_tone,
    _merge_blend_if,
    _realise_vector_cache,
    _resolve_group_opacity,
)
from Imervue.paint.compositing_pair import LAYER_BLEND_MODES, composite_layer_pair
from Imervue.paint.compositing_region import composite_region

__all__ = [
    "LAYER_BLEND_MODES",
    "composite_layer_pair",
    "composite_region",
    "composite_stack",
]


def composite_stack(
    layers: Iterable,
    base_shape: tuple[int, int],
    groups: dict | None = None,
) -> np.ndarray:
    """Walk a layer stack bottom→top and return the flattened RGBA buffer.

    Hidden / fully-transparent layers are skipped. The first visible
    layer is used as the base; the others are composited on top. If
    nothing is visible the result is a fully-transparent ``base_shape``
    canvas.

    ``groups`` maps group name → LayerGroup. A layer whose ``group``
    field names a hidden / zero-opacity group is skipped; otherwise
    the group's opacity multiplies into the layer's effective opacity.
    Group blend modes other than ``pass_through`` are stored verbatim
    but currently treated as ``pass_through`` (each layer keeps its
    own blend mode); a follow-up commit may add internal group
    compositing.
    """
    layer_list = list(layers)
    h, w = base_shape
    groups = groups or {}

    # Fast path: a single, fully-visible, normal-blend, no-mask layer
    # is just its own image — no conversion / blend math needed. The
    # general path below allocates a fresh float32 buffer per layer
    # which costs ~70ms on a 1024² canvas; that turned every fast
    # mouse-move during a stroke into a sub-15fps repaint.
    if len(layer_list) == 1:
        only = layer_list[0]
        if (
            only.visible
            and only.opacity >= 1.0
            and only.blend_mode == "normal"
            and getattr(only, "adjustment", None) is None
            and not getattr(only, "effects", ())
            and only.effective_mask is None
            and getattr(only, "blend_if", None) is None
            and only.group is None
            and getattr(only, "tone", None) is None
            and getattr(only, "binary", None) is None
            and only.image.shape[:2] == (h, w)
        ):
            # Vector layers stash strokes off the image; realise the
            # cache before returning so the fast path serves up-to-
            # date pixels rather than the stale empty buffer.
            _realise_vector_cache(only)
            return only.image

    out = np.zeros((h, w, 4), dtype=np.uint8)
    # Tracks the alpha of the most-recent non-clipped (visible) layer.
    # Clipping-mask layers above it use this to mask their output —
    # mirroring Photoshop / raster paint apps' "clip to layer below" model.
    # ``None`` means there is no base yet (a clip layer at the bottom
    # of the stack has nothing to clip to and is rendered unclipped).
    clip_base_alpha: np.ndarray | None = None
    for layer in layer_list:
        result = _composite_one_layer(out, layer, base_shape, clip_base_alpha, groups)
        if result is None:
            continue
        out, clip_base_alpha = result
    return out


def _composite_one_layer(
    out: np.ndarray,
    layer,
    base_shape: tuple[int, int],
    clip_base_alpha: np.ndarray | None,
    groups: dict,
) -> tuple[np.ndarray, np.ndarray | None] | None:
    """Composite a single layer onto ``out`` and return the updated buffer
    + new clip base. Returns ``None`` to mean "skip this layer" (hidden,
    out of group, fully transparent)."""
    group_opacity = _resolve_group_opacity(layer, groups)
    if group_opacity is None:
        return None
    if not layer.visible or layer.opacity <= 0:
        return None
    adjustment = getattr(layer, "adjustment", None)
    if adjustment is not None:
        out = _apply_adjustment_layer(out, adjustment, layer.opacity * group_opacity)
        return out, clip_base_alpha
    if layer.image.shape[:2] != base_shape:
        raise ValueError(
            f"layer {layer.name!r} shape {layer.image.shape[:2]} "
            f"does not match document {base_shape}",
        )
    _realise_vector_cache(layer)
    layer_image = _layer_image_with_tone(layer)
    effects = getattr(layer, "effects", ())
    if effects:
        from Imervue.paint.layer_effects import apply_effects
        layer_image = apply_effects(layer_image, effects)

    effective_mask = getattr(layer, "effective_mask", layer.mask)
    effective_mask = _apply_clip(layer, effective_mask, clip_base_alpha)
    effective_mask = _merge_blend_if(layer, layer_image, out, effective_mask)

    out = composite_layer_pair(
        out, layer_image,
        opacity=layer.opacity * group_opacity,
        blend_mode=layer.blend_mode,
        mask=effective_mask,
    )
    if not getattr(layer, "clip", False):
        clip_base_alpha = layer.image[..., 3].copy()
    return out, clip_base_alpha

