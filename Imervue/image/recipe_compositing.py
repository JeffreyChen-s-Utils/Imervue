"""Recipe compositing stages and their failure policy."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


logger = logging.getLogger("Imervue.recipe")


def _apply_layer_stack(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Apply user-stacked overlay layers from recipe.extra['layers'] if present."""
    raw = recipe.extra.get("layers") if recipe.extra else None
    if not raw:
        return arr
    try:
        from Imervue.image.layers import apply_layers, layers_from_dict_list
    except ImportError:
        return arr
    layers = layers_from_dict_list(raw)
    if not layers:
        return arr
    try:
        return apply_layers(arr, layers)
    except (ValueError, TypeError) as err:
        logger.warning("Layer stack apply failed: %s", err)
        return arr


def _apply_masks(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Apply local adjustment masks from recipe.extra['masks'] if present."""
    raw = recipe.extra.get("masks") if recipe.extra else None
    if not raw:
        return arr
    try:
        from Imervue.image.masks import apply_masks, masks_from_dict_list
    except ImportError:
        return arr
    masks = masks_from_dict_list(raw)
    if not masks:
        return arr
    try:
        return apply_masks(arr, masks)
    except (ValueError, TypeError) as err:
        logger.warning("Mask apply failed: %s", err)
        return arr
