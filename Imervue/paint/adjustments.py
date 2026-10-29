"""Pure-numpy non-destructive adjustment kinds + apply pipeline.

An :class:`Adjustment` is a lightweight, frozen dataclass that names
one of the supported transforms (``levels`` / ``curves`` / ``hsv``)
plus a parameter dict. The compositor applies these to the running
canvas buffer at render time, so the user can tune the parameters
later without reflowing every layer underneath — the destructive
"flatten" + "filter" loop is no longer required.

Kinds (all operate on 8-bit RGB; the alpha channel is left untouched
since adjustment layers shouldn't change visibility):

* ``levels``:   ``input_black``, ``input_white``, ``gamma``,
                ``output_black``, ``output_white`` — Photoshop's
                Levels dialog.
* ``curves``:   ``points`` — list of ``[input, output]`` control
                points in ``[0, 255]``; piecewise-linear LUT in between.
* ``hsv``:      ``hue_shift_deg``, ``saturation``, ``lightness`` —
                rotate hue + scale S / V channels.

The dispatch entry point is :func:`apply_adjustment`. New kinds can
be added by extending ``ADJUSTMENT_KINDS`` + the dispatch table.

This module keeps the tonal kinds (levels, curves, brightness /
contrast, posterize, threshold); the colour kinds and HSV / HSL
conversions live in :mod:`Imervue.paint.adjustments_color`, the
gradient map in :mod:`Imervue.paint.adjustments_gradient` and the
registry in :mod:`Imervue.paint.adjustments_params`. Every public name
is re-exported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from Imervue.paint.adjustments_color import (
    _apply_channel_mixer,
    _apply_color_balance,
    _apply_hsl,
    _apply_hsv,
    _apply_photo_filter,
    _apply_selective_color,
    _hsl_to_rgb,
    _hsv_to_rgb,
    _rgb_to_hsl,
    _rgb_to_hsv,
)
from Imervue.paint.adjustments_gradient import _apply_gradient_map
from Imervue.paint.adjustments_params import (
    ADJUSTMENT_KINDS,
    DEFAULT_PARAMS,
    SELECTIVE_RANGE_CENTERS,
    SELECTIVE_RANGES,
)

__all__ = [
    "ADJUSTMENT_KINDS",
    "DEFAULT_PARAMS",
    "SELECTIVE_RANGES",
    "SELECTIVE_RANGE_CENTERS",
    "Adjustment",
    "_hsl_to_rgb",
    "_hsv_to_rgb",
    "_rgb_to_hsl",
    "_rgb_to_hsv",
    "apply_adjustment",
]


@dataclass(frozen=True)
class Adjustment:
    """One non-destructive adjustment + its parameter dict."""

    kind: str
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ADJUSTMENT_KINDS:
            raise ValueError(
                f"unknown adjustment kind {self.kind!r}; "
                f"expected one of {ADJUSTMENT_KINDS}",
            )
        if not isinstance(self.params, dict):
            raise ValueError(
                f"params must be a dict, got {type(self.params).__name__}",
            )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, raw: dict) -> Adjustment:
        if not isinstance(raw, dict):
            raise ValueError(
                f"adjustment payload must be a dict, got {type(raw).__name__}",
            )
        kind = str(raw.get("kind", "")).strip()
        if kind not in ADJUSTMENT_KINDS:
            raise ValueError(f"unknown adjustment kind {kind!r}")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        merged = {**DEFAULT_PARAMS[kind], **params}
        return cls(kind=kind, params=merged)


# ---------------------------------------------------------------------------
# Apply dispatch
# ---------------------------------------------------------------------------


def apply_adjustment(
    image: np.ndarray, adjustment: Adjustment,
) -> np.ndarray:
    """Return a fresh HxWx4 uint8 image with the adjustment applied.

    The alpha channel is preserved. Out-of-range parameters are
    clamped to safe values so a corrupt persisted Adjustment can't
    explode the renderer.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    apply = _APPLY_BY_KIND.get(adjustment.kind)
    if apply is None:
        raise ValueError(f"unknown adjustment kind {adjustment.kind!r}")
    return apply(image, adjustment.params)


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------


def _apply_levels(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["levels"], **params}
    in_black = max(0, min(255, int(p.get("input_black", 0))))
    in_white = max(in_black + 1, min(255, int(p.get("input_white", 255))))
    out_black = max(0, min(255, int(p.get("output_black", 0))))
    out_white = max(0, min(255, int(p.get("output_white", 255))))
    gamma = max(0.01, min(10.0, float(p.get("gamma", 1.0))))

    rgb = image[..., :3].astype(np.float32) / 255.0
    in_b = in_black / 255.0
    in_w = in_white / 255.0
    out_b = out_black / 255.0
    out_w = out_white / 255.0

    stretched = np.clip((rgb - in_b) / max(in_w - in_b, 1e-6), 0.0, 1.0)
    gamma_corrected = np.power(stretched, 1.0 / gamma)
    mapped = out_b + gamma_corrected * (out_w - out_b)

    out = image.copy()
    out[..., :3] = np.clip(mapped * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Curves
# ---------------------------------------------------------------------------


def _apply_curves(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["curves"], **params}
    base_points = p.get("points") or DEFAULT_PARAMS["curves"]["points"]
    base_lut = _build_curve_lut(base_points)
    # Per-channel curves override the base. Falling back to the base
    # LUT keeps the legacy single-curve API working without changes.
    r_lut = _build_curve_lut(p.get("points_r"), fallback=base_lut)
    g_lut = _build_curve_lut(p.get("points_g"), fallback=base_lut)
    b_lut = _build_curve_lut(p.get("points_b"), fallback=base_lut)

    out = image.copy()
    out[..., 0] = r_lut[image[..., 0]]
    out[..., 1] = g_lut[image[..., 1]]
    out[..., 2] = b_lut[image[..., 2]]
    return out


def _build_curve_lut(
    raw_points,
    *,
    fallback: np.ndarray | None = None,
) -> np.ndarray:
    """Compile a list of [in, out] control points into a 256-entry uint8
    LUT. Falls back to ``fallback`` (or the identity LUT if no fallback
    is supplied) when the input has fewer than 2 valid points."""
    if not raw_points:
        if fallback is not None:
            return fallback
        return np.arange(256, dtype=np.uint8)
    points = sorted(
        (
            (max(0, min(255, int(pt[0]))), max(0, min(255, int(pt[1]))))
            for pt in raw_points
            if isinstance(pt, list | tuple) and len(pt) == 2
        ),
        key=lambda pt: pt[0],
    )
    if len(points) < 2:
        if fallback is not None:
            return fallback
        return np.arange(256, dtype=np.uint8)
    xs = np.array([pt[0] for pt in points], dtype=np.float32)
    ys = np.array([pt[1] for pt in points], dtype=np.float32)
    lut = np.interp(np.arange(256, dtype=np.float32), xs, ys)
    return np.clip(lut, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------------------
# Brightness / Contrast
# ---------------------------------------------------------------------------


def _apply_brightness_contrast(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["brightness_contrast"], **params}
    brightness = max(-1.0, min(1.0, float(p.get("brightness", 0.0))))
    contrast = max(-1.0, min(1.0, float(p.get("contrast", 0.0))))
    rgb = image[..., :3].astype(np.float32) / 255.0
    # Pivot contrast around mid-grey: contrast > 0 stretches around
    # 0.5; contrast < 0 compresses toward 0.5.
    contrast_factor = 1.0 + contrast
    rgb = (rgb - 0.5) * contrast_factor + 0.5 + brightness
    out = image.copy()
    out[..., :3] = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    return out

# ---------------------------------------------------------------------------
# Posterize
# ---------------------------------------------------------------------------


def _apply_posterize(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["posterize"], **params}
    levels = max(2, min(256, int(p.get("levels", 4))))
    rgb = image[..., :3].astype(np.float32) / 255.0
    quantised = np.round(rgb * (levels - 1)) / (levels - 1) * 255.0
    out = image.copy()
    out[..., :3] = np.clip(quantised, 0.0, 255.0).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------------


def _apply_threshold(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["threshold"], **params}
    threshold = max(0, min(255, int(p.get("threshold", 128))))
    rgb = image[..., :3].astype(np.float32)
    luminance = (
        0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    )
    above = luminance > float(threshold)
    out = image.copy()
    out[..., 0] = np.where(above, 255, 0).astype(np.uint8)
    out[..., 1] = np.where(above, 255, 0).astype(np.uint8)
    out[..., 2] = np.where(above, 255, 0).astype(np.uint8)
    return out


# Kind -> apply function, in ADJUSTMENT_KINDS order.
_APPLY_BY_KIND = {
    "levels": _apply_levels,
    "curves": _apply_curves,
    "hsv": _apply_hsv,
    "brightness_contrast": _apply_brightness_contrast,
    "color_balance": _apply_color_balance,
    "selective_color": _apply_selective_color,
    "photo_filter": _apply_photo_filter,
    "hsl": _apply_hsl,
    "gradient_map": _apply_gradient_map,
    "channel_mixer": _apply_channel_mixer,
    "posterize": _apply_posterize,
    "threshold": _apply_threshold,
}
