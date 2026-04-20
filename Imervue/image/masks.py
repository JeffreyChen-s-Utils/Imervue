"""Local adjustment masks — brush, radial, linear gradient.

A *mask* is an alpha map in ``[0, 1]`` that weights a local set of develop
adjustments (exposure / brightness / contrast / saturation / temperature /
tint). Each mask has a shape (brush / radial / linear) and its own
adjustment deltas. Masks are stored on ``Recipe.extra['masks']`` as a
list of dicts so they round-trip through recipe JSON without bloating the
core ``Recipe`` dataclass.

Three mask types:

- ``brush``: one or more circular dabs (x, y, radius) unioned together,
  with a feather falloff along the edge.
- ``radial``: an ellipse centered at (cx, cy) with radii (rx, ry) and a
  feather band. ``invert=True`` selects outside the ellipse.
- ``linear``: a linear gradient between two points with feather width.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger("Imervue.masks")

_MASK_TYPES = {"brush", "radial", "linear"}
_MAX_MASKS = 32
_MAX_BRUSH_POINTS = 512
_FEATHER_MIN = 1e-3


@dataclass
class MaskAdjustments:
    """Local adjustment deltas applied where the mask alpha is nonzero."""

    exposure: float = 0.0      # -2..+2 stops
    brightness: float = 0.0    # -1..+1
    contrast: float = 0.0      # -1..+1
    saturation: float = 0.0    # -1..+1
    temperature: float = 0.0   # -1..+1
    tint: float = 0.0          # -1..+1

    def is_zero(self) -> bool:
        return all(
            abs(getattr(self, f)) < 1e-6
            for f in ("exposure", "brightness", "contrast",
                      "saturation", "temperature", "tint")
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "exposure": float(self.exposure),
            "brightness": float(self.brightness),
            "contrast": float(self.contrast),
            "saturation": float(self.saturation),
            "temperature": float(self.temperature),
            "tint": float(self.tint),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaskAdjustments":
        return cls(
            exposure=float(data.get("exposure", 0.0)),
            brightness=float(data.get("brightness", 0.0)),
            contrast=float(data.get("contrast", 0.0)),
            saturation=float(data.get("saturation", 0.0)),
            temperature=float(data.get("temperature", 0.0)),
            tint=float(data.get("tint", 0.0)),
        )


@dataclass
class Mask:
    """A local adjustment mask. ``params`` shape depends on ``mask_type``."""

    mask_type: str                              # brush / radial / linear
    params: dict[str, Any] = field(default_factory=dict)
    adjustments: MaskAdjustments = field(default_factory=MaskAdjustments)
    invert: bool = False
    feather: float = 0.5                        # 0..1 fraction of radius/band

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.mask_type,
            "params": dict(self.params),
            "adj": self.adjustments.to_dict(),
            "invert": bool(self.invert),
            "feather": float(self.feather),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Mask":
        mtype = str(data.get("type", "brush"))
        if mtype not in _MASK_TYPES:
            mtype = "brush"
        return cls(
            mask_type=mtype,
            params=dict(data.get("params") or {}),
            adjustments=MaskAdjustments.from_dict(data.get("adj") or {}),
            invert=bool(data.get("invert", False)),
            feather=max(0.0, min(1.0, float(data.get("feather", 0.5)))),
        )


def masks_to_dict_list(masks: list[Mask]) -> list[dict[str, Any]]:
    return [m.to_dict() for m in masks[:_MAX_MASKS]]


def masks_from_dict_list(items: list[dict[str, Any]]) -> list[Mask]:
    out: list[Mask] = []
    for it in (items or [])[:_MAX_MASKS]:
        if not isinstance(it, dict):
            continue
        try:
            out.append(Mask.from_dict(it))
        except (KeyError, ValueError, TypeError):
            continue
    return out


# ----------------------------------------------------------------------
# Alpha generation
# ----------------------------------------------------------------------


def _feather_curve(d: np.ndarray, inside: float, outside: float) -> np.ndarray:
    """Smooth 0..1 falloff across the band [inside, outside]."""
    if outside - inside < _FEATHER_MIN:
        return (d <= inside).astype(np.float32)
    t = np.clip((outside - d) / (outside - inside), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def _brush_alpha(shape: tuple[int, int], mask: Mask) -> np.ndarray:
    h, w = shape
    alpha = np.zeros((h, w), dtype=np.float32)
    points = mask.params.get("points") or []
    feather = max(0.0, min(1.0, mask.feather))
    y_idx, x_idx = np.indices((h, w), dtype=np.float32)
    for pt in points[:_MAX_BRUSH_POINTS]:
        px = float(pt.get("x", 0.0))
        py = float(pt.get("y", 0.0))
        radius = max(1.0, float(pt.get("r", 20.0)))
        dist = np.sqrt((x_idx - px) ** 2 + (y_idx - py) ** 2)
        inside = radius * (1.0 - feather)
        outside = radius
        dab = _feather_curve(dist, inside, outside)
        np.maximum(alpha, dab, out=alpha)
    return alpha


def _radial_alpha(shape: tuple[int, int], mask: Mask) -> np.ndarray:
    h, w = shape
    params = mask.params
    cx = float(params.get("cx", w / 2.0))
    cy = float(params.get("cy", h / 2.0))
    rx = max(1.0, float(params.get("rx", w / 4.0)))
    ry = max(1.0, float(params.get("ry", h / 4.0)))
    y_idx, x_idx = np.indices((h, w), dtype=np.float32)
    norm = np.sqrt(((x_idx - cx) / rx) ** 2 + ((y_idx - cy) / ry) ** 2)
    feather = max(0.0, min(1.0, mask.feather))
    inside = 1.0 - feather
    outside = 1.0
    alpha = _feather_curve(norm, inside, outside)
    return alpha


def _linear_alpha(shape: tuple[int, int], mask: Mask) -> np.ndarray:
    h, w = shape
    params = mask.params
    x0 = float(params.get("x0", 0.0))
    y0 = float(params.get("y0", h / 2.0))
    x1 = float(params.get("x1", float(w)))
    y1 = float(params.get("y1", h / 2.0))
    dx, dy = x1 - x0, y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq < _FEATHER_MIN:
        return np.zeros((h, w), dtype=np.float32)
    y_idx, x_idx = np.indices((h, w), dtype=np.float32)
    # Project each pixel onto the line, normalised 0..1 along the gradient.
    t = ((x_idx - x0) * dx + (y_idx - y0) * dy) / length_sq
    feather = max(0.0, min(1.0, mask.feather))
    # Fully opaque at t<=0, transparent at t>=1 with a feather band around t=0.5
    start = max(0.0, 0.5 - feather / 2.0)
    end = min(1.0, 0.5 + feather / 2.0)
    alpha = np.where(
        t <= start,
        1.0,
        np.where(t >= end, 0.0, 1.0 - (t - start) / max(end - start, _FEATHER_MIN)),
    ).astype(np.float32)
    return alpha


_ALPHA_BUILDERS = {
    "brush": _brush_alpha,
    "radial": _radial_alpha,
    "linear": _linear_alpha,
}


def generate_alpha(shape: tuple[int, int], mask: Mask) -> np.ndarray:
    """Build a HxW float32 alpha map in ``[0, 1]`` for *mask*."""
    builder = _ALPHA_BUILDERS.get(mask.mask_type)
    if builder is None:
        return np.zeros(shape, dtype=np.float32)
    alpha = builder(shape, mask)
    if mask.invert:
        alpha = 1.0 - alpha
    return np.clip(alpha, 0.0, 1.0)


# ----------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------


def _blend(
    base: np.ndarray, adjusted: np.ndarray, alpha: np.ndarray,
) -> np.ndarray:
    """Per-pixel alpha blend of base and adjusted RGBA."""
    a3 = alpha[..., None]
    base_f = base[..., :3].astype(np.float32)
    adj_f = adjusted[..., :3].astype(np.float32)
    out_rgb = base_f * (1.0 - a3) + adj_f * a3
    np.clip(out_rgb, 0.0, 255.0, out=out_rgb)
    out = base.copy()
    out[..., :3] = out_rgb.astype(np.uint8)
    return out


def apply_masks(arr: np.ndarray, masks: list[Mask]) -> np.ndarray:
    """Apply each mask's local adjustments, weighted by its alpha map."""
    if not masks:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_masks expects HxWx4 RGBA uint8")
    from Imervue.image.recipe_adjustments import (
        apply_white_balance,
    )
    from PIL import Image, ImageEnhance

    out = arr
    for mask in masks:
        if mask.adjustments.is_zero():
            continue
        alpha = generate_alpha(arr.shape[:2], mask)
        if not alpha.any():
            continue
        adjusted = _apply_local_adjustments(out, mask.adjustments,
                                            apply_white_balance,
                                            Image, ImageEnhance)
        out = _blend(out, adjusted, alpha)
    return out


def _apply_local_adjustments(
    arr: np.ndarray, adj: MaskAdjustments,
    apply_wb, Image, ImageEnhance,
) -> np.ndarray:
    """Apply the mask's deltas to the whole frame (the blend will localize)."""
    out = apply_wb(arr, adj.temperature, adj.tint)
    if abs(adj.exposure) > 1e-6:
        factor = 2.0 ** adj.exposure
        rgb = out[..., :3].astype(np.float32) * factor
        np.clip(rgb, 0.0, 255.0, out=rgb)
        out = out.copy()
        out[..., :3] = rgb.astype(np.uint8)
    if abs(adj.brightness) > 1e-6 or abs(adj.contrast) > 1e-6:
        img = Image.fromarray(out, mode="RGBA")
        if abs(adj.brightness) > 1e-6:
            img = ImageEnhance.Brightness(img).enhance(1.0 + adj.brightness)
        if abs(adj.contrast) > 1e-6:
            img = ImageEnhance.Contrast(img).enhance(1.0 + adj.contrast)
        out = np.array(img)
    if abs(adj.saturation) > 1e-6:
        img = Image.fromarray(out, mode="RGBA")
        out = np.array(ImageEnhance.Color(img).enhance(1.0 + adj.saturation))
    return out
