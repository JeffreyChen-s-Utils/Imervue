"""Threshold and posterize tonal reductions.

Two related effects living in one module because they both collapse a
continuous tonal range to discrete steps:

* :func:`apply_threshold` — every channel pixel becomes either 0 or 255
  depending on whether its luminance falls above or below ``level``. Used
  for high-contrast B&W or screen-printed looks.
* :func:`apply_posterize` — each channel is quantised to ``levels``
  evenly-spaced steps. Used for poster / pop-art styles.

Both operate on ``HxWx4`` uint8 RGBA arrays, return a new array, and skip
the work when the configured options are no-ops so the develop pipeline
isn't surprised by allocations on identity recipes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.posterize")

THRESHOLD_MIN = 0
THRESHOLD_MAX = 255
POSTERIZE_MIN_LEVELS = 2
POSTERIZE_MAX_LEVELS = 64


# ---------------------------------------------------------------------------
# Option dataclasses (mirror the recipe.extra dict shape exactly)
# ---------------------------------------------------------------------------


@dataclass
class ThresholdOptions:
    enabled: bool = False
    level: int = 128  # luminance cutoff, 0..255

    def to_dict(self) -> dict:
        return {"enabled": bool(self.enabled), "level": int(self.level)}

    @classmethod
    def from_dict(cls, data: dict | None) -> ThresholdOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                level=_clamp_int(data.get("level", 128),
                                 THRESHOLD_MIN, THRESHOLD_MAX),
            )
        except (TypeError, ValueError):
            return cls()


@dataclass
class PosterizeOptions:
    enabled: bool = False
    levels: int = 4  # number of discrete steps per channel

    def to_dict(self) -> dict:
        return {"enabled": bool(self.enabled), "levels": int(self.levels)}

    @classmethod
    def from_dict(cls, data: dict | None) -> PosterizeOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                levels=_clamp_int(data.get("levels", 4),
                                  POSTERIZE_MIN_LEVELS, POSTERIZE_MAX_LEVELS),
            )
        except (TypeError, ValueError):
            return cls()


def _clamp_int(value, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


# ---------------------------------------------------------------------------
# Pixel ops
# ---------------------------------------------------------------------------


def apply_threshold(arr: np.ndarray, options: ThresholdOptions) -> np.ndarray:
    """Binarise ``arr`` by Rec.709 luminance against ``options.level``."""
    if not options.enabled:
        return arr
    _validate_rgba_uint8(arr)
    luma = (
        0.2126 * arr[..., 0]
        + 0.7152 * arr[..., 1]
        + 0.0722 * arr[..., 2]
    )
    mask = luma >= options.level
    out = arr.copy()
    out[..., :3] = np.where(mask[..., None], 255, 0).astype(np.uint8)
    return out


def apply_posterize(arr: np.ndarray, options: PosterizeOptions) -> np.ndarray:
    """Quantise each RGB channel to ``options.levels`` evenly-spaced steps."""
    if not options.enabled:
        return arr
    _validate_rgba_uint8(arr)
    levels = max(POSTERIZE_MIN_LEVELS,
                 min(POSTERIZE_MAX_LEVELS, int(options.levels)))
    # Each step is 256 / levels wide; we floor-divide then re-multiply
    # to snap each pixel to the nearest step's bottom edge.
    step = 256 // levels
    rgb = arr[..., :3].astype(np.uint16)
    snapped = (rgb // step) * step
    # Stretch the highest step to 255 so pure-white never becomes 240-ish.
    snapped = np.where(snapped > (255 - step), 255, snapped)
    out = arr.copy()
    out[..., :3] = snapped.astype(np.uint8)
    return out


def _validate_rgba_uint8(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"expected HxWx4 uint8 RGBA, got shape={arr.shape} dtype={arr.dtype}"
        )
