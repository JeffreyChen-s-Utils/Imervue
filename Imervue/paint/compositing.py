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
            and only.image.shape[:2] == (h, w)
        ):
            return only.image

    out = np.zeros((h, w, 4), dtype=np.uint8)
    # Tracks the alpha of the most-recent non-clipped (visible) layer.
    # Clipping-mask layers above it use this to mask their output —
    # mirroring Photoshop / MediBang's "clip to layer below" model.
    # ``None`` means there is no base yet (a clip layer at the bottom
    # of the stack has nothing to clip to and is rendered unclipped).
    clip_base_alpha: np.ndarray | None = None
    for layer in layer_list:
        layer_group = getattr(layer, "group", None)
        group_opacity = 1.0
        if layer_group is not None and layer_group in groups:
            grp = groups[layer_group]
            if not grp.visible or grp.opacity <= 0:
                continue
            group_opacity = float(grp.opacity)
        if not layer.visible or layer.opacity <= 0:
            continue
        adjustment = getattr(layer, "adjustment", None)
        if adjustment is not None:
            from Imervue.paint.adjustments import apply_adjustment
            # An adjustment layer applies its transform to everything
            # composited so far — subsequent layers paint on top of the
            # adjusted buffer.
            adjusted = apply_adjustment(out, adjustment)
            effective_opacity = layer.opacity * group_opacity
            if effective_opacity >= 1.0:
                out = adjusted
            else:
                # Blend partially — useful for "this curve only at
                # 50% strength".
                base_f = out.astype(np.float32)
                adjusted_f = adjusted.astype(np.float32)
                mixed = base_f * (1.0 - effective_opacity) + adjusted_f * effective_opacity
                out = np.clip(mixed, 0.0, 255.0).astype(np.uint8)
            continue
        if layer.image.shape[:2] != (h, w):
            raise ValueError(
                f"layer {layer.name!r} shape {layer.image.shape[:2]} "
                f"does not match document {base_shape}",
            )
        layer_image = layer.image
        effects = getattr(layer, "effects", ())
        if effects:
            from Imervue.paint.layer_effects import apply_effects
            layer_image = apply_effects(layer_image, effects)

        # Combine the layer's effective mask with any blend-if mask.
        effective_mask = getattr(layer, "effective_mask", layer.mask)
        # Clipping mask: a layer with ``clip=True`` clips its output
        # to the alpha of the most-recent non-clipped layer below it.
        # Multiply the alpha into the effective mask so the existing
        # downstream code path handles compositing without extra logic.
        if getattr(layer, "clip", False) and clip_base_alpha is not None:
            if effective_mask is None:
                effective_mask = clip_base_alpha
            else:
                clip_combined = (
                    effective_mask.astype(np.float32) / 255.0
                    * clip_base_alpha.astype(np.float32) / 255.0
                )
                effective_mask = (
                    clip_combined * 255.0
                ).clip(0, 255).astype(np.uint8)
        blend_if = getattr(layer, "blend_if", None)
        if blend_if is not None:
            from Imervue.paint.blend_if import compute_blend_if_mask
            blend_if_alpha = compute_blend_if_mask(
                layer_image, out, blend_if,
            )
            blend_if_mask = (blend_if_alpha * 255.0).clip(0, 255).astype(np.uint8)
            if effective_mask is None:
                effective_mask = blend_if_mask
            else:
                combined = (
                    effective_mask.astype(np.float32) / 255.0
                ) * blend_if_alpha
                effective_mask = (
                    combined * 255.0
                ).clip(0, 255).astype(np.uint8)

        out = composite_layer_pair(
            out, layer_image,
            opacity=layer.opacity * group_opacity,
            blend_mode=layer.blend_mode,
            mask=effective_mask,
        )
        # A non-clipped layer becomes the new clip base for any
        # clipping layers that come above it in the stack. Clipping
        # layers do NOT update the base — they're masked by the
        # base, not contributors to it.
        if not getattr(layer, "clip", False):
            clip_base_alpha = layer.image[..., 3].copy()
    return out


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
