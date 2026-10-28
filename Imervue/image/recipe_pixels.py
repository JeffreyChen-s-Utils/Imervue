"""Pixel adjustment stages for the develop recipe pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


from PIL import Image, ImageEnhance
from Imervue.image.recipe_values import _is_zero
from Imervue.image.recipe_adjustments import (
    apply_highlights_shadows,
    apply_vibrance,
    apply_white_balance,
    apply_whites_blacks,
)
from Imervue.image.tone_curve import apply_tone_curve


def _apply_white_balance(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    return apply_white_balance(arr, recipe.temperature, recipe.tint)


def _apply_highlights_shadows(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    return apply_highlights_shadows(arr, recipe.highlights, recipe.shadows)


def _apply_whites_blacks(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    return apply_whites_blacks(arr, recipe.whites, recipe.blacks)


def _apply_vibrance(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    return apply_vibrance(arr, recipe.vibrance)


def _apply_tone_curve(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    return apply_tone_curve(
        arr,
        recipe.tone_curve_rgb,
        r_points=recipe.tone_curve_r,
        g_points=recipe.tone_curve_g,
        b_points=recipe.tone_curve_b,
    )


def _apply_exposure(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Step 5 — exposure in stops (2**exposure)."""
    if _is_zero(recipe.exposure):
        return arr
    factor = 2.0**recipe.exposure
    rgb = arr[..., :3].astype(np.float32) * factor
    np.clip(rgb, 0.0, 255.0, out=rgb)
    arr = arr.copy()
    arr[..., :3] = rgb.astype(np.uint8)
    return arr


def _apply_brightness_contrast(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Brightness / contrast via PIL enhancements."""
    if _is_zero(recipe.brightness) and _is_zero(recipe.contrast):
        return arr
    img = Image.fromarray(arr, mode="RGBA")
    if not _is_zero(recipe.brightness):
        img = ImageEnhance.Brightness(img).enhance(1.0 + recipe.brightness)
    if not _is_zero(recipe.contrast):
        img = ImageEnhance.Contrast(img).enhance(1.0 + recipe.contrast)
    return np.array(img)


def _apply_saturation(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Final saturation pass — runs after vibrance."""
    if _is_zero(recipe.saturation):
        return arr
    img = Image.fromarray(arr, mode="RGBA")
    img = ImageEnhance.Color(img).enhance(1.0 + recipe.saturation)
    return np.array(img)
