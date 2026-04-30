"""Blend-If — per-pixel layer visibility based on luminance ranges.

Photoshop's Layer Style "Blend If" sliders let the user gate a
layer's visibility against either its own luminance (``this``) or
the running composite of layers below (``underlying``). The
feathered split-sliders produce intermediate alpha — pixels whose
luminance is just inside the band fade in / out smoothly instead
of popping.

This module ships the data layer + the per-pixel mask computer.
The compositing path (in ``compositing.composite_stack``) consults
``Layer.blend_if`` and multiplies the result into the layer's
effective mask before alpha-blending.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BlendIf:
    """Per-pixel luminance-range gates for a layer.

    Each side (this layer / underlying composite) has a minimum and
    maximum luminance plus a feather range outside the band where
    alpha ramps linearly from 0 to 1. ``feather = 0`` produces a
    hard cutoff. The default values describe a fully-permissive
    gate — every pixel passes — so the field can be set to a default
    BlendIf without changing the layer's appearance.
    """

    this_min: int = 0
    this_max: int = 255
    this_min_feather: int = 0
    this_max_feather: int = 0
    underlying_min: int = 0
    underlying_max: int = 255
    underlying_min_feather: int = 0
    underlying_max_feather: int = 0

    def __post_init__(self) -> None:
        for key, value in (
            ("this_min", self.this_min),
            ("this_max", self.this_max),
            ("underlying_min", self.underlying_min),
            ("underlying_max", self.underlying_max),
        ):
            if not 0 <= int(value) <= 255:
                raise ValueError(
                    f"{key} must be in [0, 255], got {value!r}",
                )
        for key, value in (
            ("this_min_feather", self.this_min_feather),
            ("this_max_feather", self.this_max_feather),
            ("underlying_min_feather", self.underlying_min_feather),
            ("underlying_max_feather", self.underlying_max_feather),
        ):
            if int(value) < 0:
                raise ValueError(
                    f"{key} must be >= 0, got {value!r}",
                )
        if self.this_min > self.this_max:
            raise ValueError(
                f"this_min ({self.this_min}) > this_max ({self.this_max})",
            )
        if self.underlying_min > self.underlying_max:
            raise ValueError(
                f"underlying_min ({self.underlying_min}) > "
                f"underlying_max ({self.underlying_max})",
            )

    def to_dict(self) -> dict:
        return {
            "this_min": int(self.this_min),
            "this_max": int(self.this_max),
            "this_min_feather": int(self.this_min_feather),
            "this_max_feather": int(self.this_max_feather),
            "underlying_min": int(self.underlying_min),
            "underlying_max": int(self.underlying_max),
            "underlying_min_feather": int(self.underlying_min_feather),
            "underlying_max_feather": int(self.underlying_max_feather),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> BlendIf:
        if not isinstance(raw, dict):
            raise ValueError(
                f"blend_if payload must be a dict, got {type(raw).__name__}",
            )
        defaults = {
            "this_min": 0, "this_max": 255,
            "this_min_feather": 0, "this_max_feather": 0,
            "underlying_min": 0, "underlying_max": 255,
            "underlying_min_feather": 0, "underlying_max_feather": 0,
        }
        merged: dict[str, int] = {}
        for key, default in defaults.items():
            try:
                merged[key] = int(raw.get(key, default))
            except (TypeError, ValueError):
                merged[key] = default
        # Clamp to valid ranges so a corrupt persisted value doesn't
        # trip __post_init__.
        for key in ("this_min", "this_max",
                    "underlying_min", "underlying_max"):
            merged[key] = max(0, min(255, merged[key]))
        for key in ("this_min_feather", "this_max_feather",
                    "underlying_min_feather", "underlying_max_feather"):
            merged[key] = max(0, merged[key])
        merged["this_min"] = min(merged["this_min"], merged["this_max"])
        merged["underlying_min"] = min(
            merged["underlying_min"], merged["underlying_max"],
        )
        return cls(**merged)


def compute_blend_if_mask(
    layer_image: np.ndarray,
    underlying: np.ndarray | None,
    blend_if: BlendIf,
) -> np.ndarray:
    """Return a per-pixel float32 alpha multiplier in ``[0, 1]``.

    The result is the elementwise product of the this-layer mask and
    the underlying-layer mask (when ``underlying`` is provided). The
    caller multiplies it into the layer's existing mask before
    compositing.
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
    h, w = layer_image.shape[:2]
    this_lum = _luminance(layer_image)
    this_alpha = _band_pass(
        this_lum,
        blend_if.this_min, blend_if.this_max,
        blend_if.this_min_feather, blend_if.this_max_feather,
    )
    if underlying is None:
        return this_alpha
    if (
        underlying.ndim != 3
        or underlying.shape[:2] != (h, w)
        or underlying.shape[2] != 4
        or underlying.dtype != np.uint8
    ):
        raise ValueError(
            f"underlying must be the same HxWx4 uint8 RGBA shape as "
            f"layer_image, got {underlying.shape} {underlying.dtype}",
        )
    und_lum = _luminance(underlying)
    und_alpha = _band_pass(
        und_lum,
        blend_if.underlying_min, blend_if.underlying_max,
        blend_if.underlying_min_feather, blend_if.underlying_max_feather,
    )
    return (this_alpha * und_alpha).astype(np.float32)


def _luminance(image: np.ndarray) -> np.ndarray:
    """Per-pixel Rec.601 luminance as a float32 buffer in [0, 255]."""
    rgb = image[..., :3].astype(np.float32)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _band_pass(
    luminance: np.ndarray,
    lo: int,
    hi: int,
    lo_feather: int,
    hi_feather: int,
) -> np.ndarray:
    """Per-pixel band-pass: 1 inside ``[lo, hi]``, 0 outside, with
    feathered linear transitions of ``lo_feather`` / ``hi_feather``
    pixels on the low / high sides."""
    alpha = np.ones_like(luminance, dtype=np.float32)

    if lo_feather > 0:
        # Pixels in [lo - lo_feather, lo) ramp from 0 to 1.
        below = luminance < float(lo)
        ramp = (luminance - (float(lo) - lo_feather)) / float(lo_feather)
        alpha = np.where(below, np.clip(ramp, 0.0, 1.0), alpha)
    else:
        alpha = np.where(luminance < float(lo), 0.0, alpha)

    if hi_feather > 0:
        above = luminance > float(hi)
        ramp = ((float(hi) + hi_feather) - luminance) / float(hi_feather)
        alpha = np.where(above, np.clip(ramp, 0.0, 1.0), alpha)
    else:
        alpha = np.where(luminance > float(hi), 0.0, alpha)

    return np.clip(alpha, 0.0, 1.0).astype(np.float32)
