"""Recipe color effects stages and their failure policy."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


logger = logging.getLogger("Imervue.recipe")


def _apply_split_toning(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Apply split toning from recipe.extra['split_toning'] if present."""
    cfg = recipe.extra.get("split_toning") if recipe.extra else None
    if not isinstance(cfg, dict):
        return arr
    try:
        from Imervue.image.split_toning import apply_split_toning
    except ImportError:
        return arr
    try:
        return apply_split_toning(
            arr,
            shadow_hue=float(cfg.get("shadow_hue", 210.0)),
            shadow_saturation=float(cfg.get("shadow_sat", 0.0)),
            highlight_hue=float(cfg.get("highlight_hue", 45.0)),
            highlight_saturation=float(cfg.get("highlight_sat", 0.0)),
            balance=float(cfg.get("balance", 0.0)),
        )
    except (ValueError, TypeError) as err:
        logger.warning("Split toning apply failed: %s", err)
        return arr


def _apply_lut(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Apply a .cube LUT if one is configured; otherwise pass-through."""
    if not recipe.lut_path:
        return arr
    try:
        from Imervue.image.lut import apply_cube_lut
    except ImportError:
        return arr
    try:
        return apply_cube_lut(arr, recipe.lut_path, intensity=recipe.lut_intensity)
    except (OSError, ValueError) as err:
        logger.warning("LUT apply failed (%s): %s", recipe.lut_path, err)
        return arr


def _apply_threshold_posterize(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Apply threshold and posterize from recipe.extra if configured."""
    if not recipe.extra:
        return arr
    try:
        from Imervue.image.posterize import (
            PosterizeOptions,
            ThresholdOptions,
            apply_posterize,
            apply_threshold,
        )
    except ImportError:
        return arr
    threshold_opts = ThresholdOptions.from_dict(recipe.extra.get("threshold"))
    posterize_opts = PosterizeOptions.from_dict(recipe.extra.get("posterize"))
    try:
        arr = apply_threshold(arr, threshold_opts)
        arr = apply_posterize(arr, posterize_opts)
    except (ValueError, TypeError) as err:
        logger.warning("Threshold/posterize apply failed: %s", err)
    return arr
