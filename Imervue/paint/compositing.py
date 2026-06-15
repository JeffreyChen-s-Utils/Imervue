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

LAYER_BLEND_MODES = (
    "normal", "multiply", "screen", "overlay",
    "darken", "lighten",
    "color_dodge", "color_burn",
    "soft_light", "hard_light",
    "linear_burn", "linear_dodge",
)


def composite_layer_pair(
    below: np.ndarray,
    above: np.ndarray,
    *,
    opacity: float = 1.0,
    blend_mode: str = "normal",
    mask: np.ndarray | None = None,
) -> np.ndarray:
    """Place ``above`` over ``below`` using ``blend_mode`` and ``opacity``.

    Both inputs must be HxWx4 uint8 RGBA of the same shape. ``mask`` is
    an optional ``HxW`` uint8 alpha buffer that further attenuates the
    above layer (used by layer masks).
    """
    _check_pair(below, above)
    if blend_mode not in LAYER_BLEND_MODES:
        raise ValueError(
            f"unknown blend_mode {blend_mode!r}; expected one of {LAYER_BLEND_MODES}",
        )
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity <= 0.0:
        return below.copy()

    h, w = below.shape[:2]
    if mask is not None:
        if mask.shape != (h, w):
            raise ValueError(
                f"mask shape {mask.shape} does not match canvas {(h, w)}",
            )
        if mask.dtype != np.uint8:
            raise ValueError(f"mask dtype must be uint8, got {mask.dtype}")

    bg_rgb = below[..., :3].astype(np.float32) / 255.0
    bg_a = below[..., 3].astype(np.float32) / 255.0
    fg_rgb = above[..., :3].astype(np.float32) / 255.0
    fg_a = above[..., 3].astype(np.float32) / 255.0
    fg_a = fg_a * opacity
    if mask is not None:
        fg_a = fg_a * (mask.astype(np.float32) / 255.0)

    blended_rgb = _blend_rgb(bg_rgb, fg_rgb, blend_mode)
    out_rgb = bg_rgb * (1.0 - fg_a)[..., None] + blended_rgb * fg_a[..., None]
    out_a = fg_a + bg_a * (1.0 - fg_a)

    out = np.empty_like(below)
    out[..., :3] = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    out[..., 3] = np.clip(out_a * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


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
            if getattr(only, "vector_data", None) is not None:
                from Imervue.paint.vector_layer import realise_vector_layer
                realise_vector_layer(only)
            return only.image

    out = np.zeros((h, w, 4), dtype=np.uint8)
    # Tracks the alpha of the most-recent non-clipped (visible) layer.
    # Clipping-mask layers above it use this to mask their output —
    # mirroring Photoshop / raster paint apps's "clip to layer below" model.
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
    # Vector layers store the canonical state in ``vector_data``;
    # the rasterised image is a cache that must be refreshed when
    # strokes change. ``realise_vector_layer`` is a no-op for raster
    # layers so the dispatch is cheap regardless.
    if getattr(layer, "vector_data", None) is not None:
        from Imervue.paint.vector_layer import realise_vector_layer
        realise_vector_layer(layer)
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

    if getattr(layer, "vector_data", None) is not None:
        from Imervue.paint.vector_layer import realise_vector_layer
        realise_vector_layer(layer)
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


# ---------------------------------------------------------------------------
# Internals — same blend curves as the brush engine, vectorised here.
# ---------------------------------------------------------------------------


def _blend_rgb(bg: np.ndarray, fg: np.ndarray, mode: str) -> np.ndarray:
    if mode == "normal":
        return fg
    if mode == "multiply":
        return bg * fg
    if mode == "screen":
        return 1.0 - (1.0 - bg) * (1.0 - fg)
    if mode == "overlay":
        return np.where(bg <= 0.5, 2.0 * bg * fg, 1.0 - 2.0 * (1.0 - bg) * (1.0 - fg))
    if mode == "darken":
        return np.minimum(bg, fg)
    if mode == "lighten":
        return np.maximum(bg, fg)
    if mode == "color_dodge":
        return np.where(fg >= 1.0, 1.0, np.minimum(1.0, bg / np.maximum(1.0 - fg, 1e-6)))
    if mode == "color_burn":
        return np.where(
            fg <= 0.0, 0.0,
            1.0 - np.minimum(1.0, (1.0 - bg) / np.maximum(fg, 1e-6)),
        )
    if mode == "soft_light":
        return np.where(
            fg <= 0.5,
            bg - (1.0 - 2.0 * fg) * bg * (1.0 - bg),
            bg + (2.0 * fg - 1.0) * (_d_curve(bg) - bg),
        )
    if mode == "hard_light":
        return np.where(fg <= 0.5, 2.0 * bg * fg, 1.0 - 2.0 * (1.0 - bg) * (1.0 - fg))
    if mode == "linear_burn":
        return np.maximum(bg + fg - 1.0, 0.0)
    if mode == "linear_dodge":
        return np.minimum(bg + fg, 1.0)
    raise ValueError(f"unknown blend_mode {mode!r}")


def _d_curve(x: np.ndarray) -> np.ndarray:
    return np.where(x <= 0.25, ((16.0 * x - 12.0) * x + 4.0) * x, np.sqrt(x))


def _check_pair(below: np.ndarray, above: np.ndarray) -> None:
    if below.ndim != 3 or below.shape[2] != 4 or below.dtype != np.uint8:
        raise ValueError(f"below must be HxWx4 uint8 RGBA, got {below.shape} {below.dtype}")
    if above.shape != below.shape or above.dtype != np.uint8:
        raise ValueError(
            f"above must match below shape/dtype: got {above.shape} {above.dtype} "
            f"vs {below.shape} {below.dtype}",
        )
