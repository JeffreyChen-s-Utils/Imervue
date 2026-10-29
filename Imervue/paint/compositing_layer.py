"""Per-layer preparation shared by the full-stack and region compositors.

Group visibility / opacity, the vector-cache refresh, tone / binary render
hints, clipping masks, blend-if masks and adjustment layers: each step turns
one layer (plus the composite so far) into the inputs of
:func:`Imervue.paint.compositing_pair.composite_layer_pair`.
"""
from __future__ import annotations

import numpy as np


def _realise_vector_cache(layer) -> None:
    """Refresh a vector layer's rasterised ``image`` cache from its strokes.

    Vector layers store the canonical state in ``vector_data``; the
    rasterised image is a cache that must be refreshed when strokes
    change. Raster layers (no ``vector_data``) are left untouched.
    """
    if getattr(layer, "vector_data", None) is not None:
        from Imervue.paint.vector_layer import realise_vector_layer
        realise_vector_layer(layer)


def _layer_image_with_tone(layer) -> np.ndarray:
    """Return ``layer.image`` after the tone / binary render hints.

    Extracted from :func:`composite_stack` so the main loop's
    cyclomatic complexity stays inside the project ceiling. The hints
    are mutually-exclusive in practice (a layer is either greyscale-
    halftone or 1-bit ink) but if both are set the binary pass runs
    on the halftone output, producing solid-ink dot silhouettes.
    """
    image = layer.image
    tone = getattr(layer, "tone", None)
    if tone is not None:
        from Imervue.paint.halftone import render_tone_layer
        image = render_tone_layer(image, tone)
    binary = getattr(layer, "binary", None)
    if binary is not None:
        from Imervue.paint.binary_layer import render_binary_layer
        image = render_binary_layer(image, binary)
    return image


def _apply_clip(
    layer, effective_mask: np.ndarray | None,
    clip_base_alpha: np.ndarray | None,
) -> np.ndarray | None:
    """Multiply the most-recent base layer's alpha into ``effective_mask``
    when ``layer.clip`` is set. Returns the (possibly new) mask.

    ``None`` ``clip_base_alpha`` (e.g. clip layer at the bottom of the
    stack) leaves the mask unchanged so the layer renders normally
    rather than disappearing — matches Photoshop's fallback.
    """
    if not getattr(layer, "clip", False) or clip_base_alpha is None:
        return effective_mask
    if effective_mask is None:
        return clip_base_alpha
    combined = (
        effective_mask.astype(np.float32) / 255.0
        * clip_base_alpha.astype(np.float32) / 255.0
    )
    return (combined * 255.0).clip(0, 255).astype(np.uint8)


def _apply_adjustment_layer(
    out: np.ndarray, adjustment, effective_opacity: float,
) -> np.ndarray:
    """Apply an adjustment layer's transform to the composite-so-far,
    blending partial opacity when the layer isn't fully opaque."""
    from Imervue.paint.adjustments import apply_adjustment
    adjusted = apply_adjustment(out, adjustment)
    if effective_opacity >= 1.0:
        return adjusted
    base_f = out.astype(np.float32)
    adjusted_f = adjusted.astype(np.float32)
    mixed = base_f * (1.0 - effective_opacity) + adjusted_f * effective_opacity
    return np.clip(mixed, 0.0, 255.0).astype(np.uint8)


def _merge_blend_if(layer, layer_image: np.ndarray, out: np.ndarray, effective_mask):
    """Combine the layer's existing mask with any blend-if mask the
    layer carries. Returns the merged uint8 mask, or the original
    when no blend-if rule is active."""
    blend_if = getattr(layer, "blend_if", None)
    if blend_if is None:
        return effective_mask
    from Imervue.paint.blend_if import compute_blend_if_mask
    blend_if_alpha = compute_blend_if_mask(layer_image, out, blend_if)
    blend_if_mask = (blend_if_alpha * 255.0).clip(0, 255).astype(np.uint8)
    if effective_mask is None:
        return blend_if_mask
    combined = (effective_mask.astype(np.float32) / 255.0) * blend_if_alpha
    return (combined * 255.0).clip(0, 255).astype(np.uint8)


def _resolve_group_opacity(layer, groups: dict) -> float | None:
    """Return the layer's effective group-opacity multiplier, or None
    when the group is hidden / zero-opacity (caller should skip)."""
    layer_group = getattr(layer, "group", None)
    if layer_group is None or layer_group not in groups:
        return 1.0
    grp = groups[layer_group]
    if not grp.visible or grp.opacity <= 0:
        return None
    return float(grp.opacity)
