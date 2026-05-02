"""Non-destructive layer effects — drop shadow / outer glow / stroke.

Each effect adds painted pixels *around* a layer's alpha mask before
the layer is composited. The effects don't mutate the layer's image —
they're stored as :class:`LayerEffect` instances on
:attr:`Layer.effects` and applied via :func:`apply_effects` at
composite time, mirroring how Phase 10c's adjustment layers stay
non-destructive.

Three kinds ship in this commit:

* ``drop_shadow`` — soft offset shadow behind the layer's silhouette.
  Params: ``offset_x``, ``offset_y``, ``radius`` (blur), ``opacity``,
  ``color`` (RGBA).
* ``outer_glow``  — like drop shadow but offset 0, color usually
  warm. Params: ``radius``, ``opacity``, ``color``, ``intensity``
  (gain over baseline alpha for a brighter halo).
* ``stroke``      — coloured outline tracing the layer's alpha
  boundary. Params: ``width``, ``opacity``, ``color``,
  ``placement`` (``outside`` / ``inside`` / ``center``).

The effects render as a fresh HxWx4 RGBA buffer; the original layer
image is left untouched. Compositing builds (effect_layers below) +
(layer image on top) per Photoshop convention so the effect colours
appear around the silhouette without recolouring the layer's
existing pixels.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from Imervue.paint.compositing import composite_layer_pair
from Imervue.paint.selection_ops import _box_blur, _dilate_once, _erode_once

EFFECT_KINDS = ("drop_shadow", "outer_glow", "stroke")
STROKE_PLACEMENTS = ("outside", "inside", "center")

DEFAULT_PARAMS: dict[str, dict] = {
    "drop_shadow": {
        "offset_x": 6,
        "offset_y": 6,
        "radius": 6,
        "opacity": 0.6,
        "color": [0, 0, 0, 255],
    },
    "outer_glow": {
        "radius": 8,
        "opacity": 0.6,
        "intensity": 1.5,
        "color": [255, 220, 120, 255],
    },
    "stroke": {
        "width": 3,
        "opacity": 1.0,
        "placement": "outside",
        "color": [0, 0, 0, 255],
    },
}

# Hard caps to keep an iterative dilation / blur from spinning out
# under a corrupted persisted parameter.
MAX_RADIUS = 64
MAX_STROKE_WIDTH = 32


@dataclass(frozen=True)
class LayerEffect:
    """One non-destructive layer effect entry.

    ``params`` is a dict (mutable inside the frozen dataclass) — the
    frozen-ness only forbids reassigning the dict reference, which
    matches Adjustment's contract.
    """

    kind: str
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in EFFECT_KINDS:
            raise ValueError(
                f"unknown layer-effect kind {self.kind!r}; "
                f"expected one of {EFFECT_KINDS}",
            )
        if not isinstance(self.params, dict):
            raise ValueError(
                f"params must be a dict, got {type(self.params).__name__}",
            )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, raw: dict) -> LayerEffect:
        if not isinstance(raw, dict):
            raise ValueError(
                f"effect payload must be a dict, got {type(raw).__name__}",
            )
        kind = str(raw.get("kind", "")).strip()
        if kind not in EFFECT_KINDS:
            raise ValueError(f"unknown layer-effect kind {kind!r}")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        merged = {**DEFAULT_PARAMS[kind], **params}
        return cls(kind=kind, params=merged)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_effects(
    layer_image: np.ndarray,
    effects: tuple[LayerEffect, ...] | list[LayerEffect],
) -> np.ndarray:
    """Return ``layer_image`` with effects rendered behind / around it.

    The order of the returned buffer mirrors Photoshop's "fx pane":
    effects render in a fixed bottom-up order (drop_shadow, then
    outer_glow, then stroke, then the layer pixels) regardless of
    the order in ``effects`` — the caller can disable an effect by
    omitting it from the tuple.
    """
    if (
        layer_image.ndim != 3
        or layer_image.shape[2] != 4
        or layer_image.dtype != np.uint8
    ):
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, "
            f"got {layer_image.shape} {layer_image.dtype}",
        )
    if not effects:
        return layer_image
    by_kind: dict[str, LayerEffect] = {}
    for effect in effects:
        # First-occurrence wins so a duplicate doesn't silently take
        # over the user-visible behaviour of the layer.
        if effect.kind not in by_kind:
            by_kind[effect.kind] = effect

    h, w = layer_image.shape[:2]
    out = np.zeros((h, w, 4), dtype=np.uint8)

    # Render the stroke once and route it above / below the layer
    # depending on placement: outside-stroke peeks past the layer's
    # silhouette so it sits behind the layer pixels (no occlusion);
    # inside / center strokes overwrite layer pixels along the
    # silhouette's interior so they have to render on top.
    stroke_effect = by_kind.get("stroke")
    stroke_placement = (
        str(stroke_effect.params.get("placement", "outside"))
        if stroke_effect is not None else "outside"
    )

    if "drop_shadow" in by_kind:
        out = composite_layer_pair(
            out, _render_drop_shadow(layer_image, by_kind["drop_shadow"]),
        )
    if "outer_glow" in by_kind:
        out = composite_layer_pair(
            out, _render_outer_glow(layer_image, by_kind["outer_glow"]),
        )
    if stroke_effect is not None and stroke_placement == "outside":
        out = composite_layer_pair(out, _render_stroke(layer_image, stroke_effect))

    out = composite_layer_pair(out, layer_image)

    if stroke_effect is not None and stroke_placement != "outside":
        out = composite_layer_pair(out, _render_stroke(layer_image, stroke_effect))

    # composite_layer_pair leaves the RGB pre-multiplied by alpha when
    # composited onto a transparent base. The result needs to ride
    # through another composite (canvas) downstream as a *straight*
    # RGBA buffer — undo the multiplication so the colours stay true.
    return _unpremultiply(out)


# ---------------------------------------------------------------------------
# Drop shadow
# ---------------------------------------------------------------------------


def _render_drop_shadow(
    layer_image: np.ndarray, effect: LayerEffect,
) -> np.ndarray:
    p = {**DEFAULT_PARAMS["drop_shadow"], **effect.params}
    h, w = layer_image.shape[:2]
    offset_x = max(-w, min(w, int(p.get("offset_x", 0))))
    offset_y = max(-h, min(h, int(p.get("offset_y", 0))))
    radius = max(0, min(MAX_RADIUS, int(p.get("radius", 0))))
    opacity = max(0.0, min(1.0, float(p.get("opacity", 1.0))))
    color = _coerce_rgba(p.get("color"))

    alpha = layer_image[..., 3].astype(np.float32) / 255.0
    blurred = _box_blur(alpha, radius) if radius > 0 else alpha
    shifted = _shift_alpha(blurred, offset_x, offset_y)
    result_alpha = np.clip(shifted * opacity, 0.0, 1.0)
    return _alpha_to_rgba(result_alpha, color)


def _shift_alpha(alpha: np.ndarray, dx: int, dy: int) -> np.ndarray:
    h, w = alpha.shape
    shifted = np.zeros_like(alpha)
    src_y0 = max(0, -dy)
    src_y1 = min(h, h - dy)
    src_x0 = max(0, -dx)
    src_x1 = min(w, w - dx)
    dst_y0 = max(0, dy)
    dst_x0 = max(0, dx)
    if src_y1 <= src_y0 or src_x1 <= src_x0:
        return shifted
    shifted[
        dst_y0:dst_y0 + (src_y1 - src_y0),
        dst_x0:dst_x0 + (src_x1 - src_x0),
    ] = alpha[src_y0:src_y1, src_x0:src_x1]
    return shifted


# ---------------------------------------------------------------------------
# Outer glow
# ---------------------------------------------------------------------------


def _render_outer_glow(
    layer_image: np.ndarray, effect: LayerEffect,
) -> np.ndarray:
    p = {**DEFAULT_PARAMS["outer_glow"], **effect.params}
    radius = max(0, min(MAX_RADIUS, int(p.get("radius", 0))))
    opacity = max(0.0, min(1.0, float(p.get("opacity", 1.0))))
    intensity = max(0.0, min(8.0, float(p.get("intensity", 1.0))))
    color = _coerce_rgba(p.get("color"))

    alpha = layer_image[..., 3].astype(np.float32) / 255.0
    blurred = _box_blur(alpha, radius) if radius > 0 else alpha
    glow = np.clip(blurred * intensity * opacity, 0.0, 1.0)
    return _alpha_to_rgba(glow, color)


# ---------------------------------------------------------------------------
# Stroke
# ---------------------------------------------------------------------------


def _render_stroke(
    layer_image: np.ndarray, effect: LayerEffect,
) -> np.ndarray:
    p = {**DEFAULT_PARAMS["stroke"], **effect.params}
    width = max(0, min(MAX_STROKE_WIDTH, int(p.get("width", 0))))
    opacity = max(0.0, min(1.0, float(p.get("opacity", 1.0))))
    placement = str(p.get("placement", "outside"))
    if placement not in STROKE_PLACEMENTS:
        placement = "outside"
    color = _coerce_rgba(p.get("color"))

    h, w = layer_image.shape[:2]
    if width <= 0:
        return np.zeros((h, w, 4), dtype=np.uint8)
    alpha_mask = layer_image[..., 3] > 0
    band = _stroke_band_mask(alpha_mask, width, placement)
    band_alpha = band.astype(np.float32) * opacity
    return _alpha_to_rgba(band_alpha, color)


def _stroke_band_mask(
    alpha_mask: np.ndarray, width: int, placement: str,
) -> np.ndarray:
    """Compute the per-placement boolean band the stroke fills."""
    if placement == "outside":
        outer = alpha_mask.copy()
        for _ in range(width):
            outer = _dilate_once(outer)
        return outer & ~alpha_mask
    if placement == "inside":
        inner = alpha_mask.copy()
        for _ in range(width):
            inner = _erode_once(inner)
        return alpha_mask & ~inner
    # center — half outside, half inside (favours outside on odd widths).
    half_outside = width - width // 2
    half_inside = width // 2
    outer = alpha_mask.copy()
    for _ in range(half_outside):
        outer = _dilate_once(outer)
    inner = alpha_mask.copy()
    for _ in range(half_inside):
        inner = _erode_once(inner)
    return outer & ~inner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _alpha_to_rgba(
    alpha: np.ndarray, color: tuple[int, int, int, int],
) -> np.ndarray:
    """Build an HxWx4 RGBA image from a float alpha map + a flat colour."""
    h, w = alpha.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0] = color[0]
    out[..., 1] = color[1]
    out[..., 2] = color[2]
    out[..., 3] = np.clip(
        alpha * (color[3] / 255.0) * 255.0, 0.0, 255.0,
    ).astype(np.uint8)
    return out


def _unpremultiply(rgba: np.ndarray) -> np.ndarray:
    """Restore straight-alpha RGBA by dividing RGB by alpha.

    Pixels with alpha == 0 keep their (zero) RGB instead of dividing
    by zero. The result rounds back to uint8."""
    out = rgba.astype(np.float32)
    alpha = out[..., 3:4] / 255.0
    safe = np.where(alpha < 1e-6, 1.0, alpha)
    out[..., :3] = out[..., :3] / safe
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def _coerce_rgba(raw) -> tuple[int, int, int, int]:
    """Normalise a colour payload into an RGBA tuple, clamping values."""
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        try:
            return tuple(max(0, min(255, int(c))) for c in raw)   # type: ignore[return-value]
        except (TypeError, ValueError):
            return (0, 0, 0, 255)
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        try:
            return (
                *(max(0, min(255, int(c))) for c in raw),
                255,
            )   # type: ignore[return-value]
        except (TypeError, ValueError):
            return (0, 0, 0, 255)
    return (0, 0, 0, 255)
