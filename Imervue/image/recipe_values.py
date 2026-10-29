"""Recipe value categories and neutral slider tolerance."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


_ADJUST_EPS = 1e-6
CLASSIC_SLIDERS = ("brightness", "contrast", "saturation", "exposure")
ADVANCED_SLIDERS = ("temperature", "tint", "highlights", "shadows", "whites", "blacks", "vibrance")
CURVES = ("tone_curve_rgb", "tone_curve_r", "tone_curve_g", "tone_curve_b")
_ENABLED_EXTRAS = (
    "threshold",
    "posterize",
    "levels",
    "channel_mixer",
    "gradient_map",
    "film_grain",
    "lens_flare",
)


def _is_zero(value: float) -> bool:
    """Return True if *value* is effectively zero within adjust tolerance."""
    return math.isclose(value, 0.0, abs_tol=_ADJUST_EPS)


def _enabled_flag(entry: object) -> bool:
    """Return True when ``entry`` is a dict whose ``enabled`` field is truthy."""
    return bool(isinstance(entry, dict) and entry.get("enabled"))



def extra_is_identity(extra) -> bool:
    if not extra:
        return True
    if any(extra.get(key) for key in ("layers", "masks", "split_toning")):
        return False
    return not any(_enabled_flag(extra.get(key)) for key in _ENABLED_EXTRAS)



def normalized(recipe: Recipe) -> Recipe:
    """Return a copy with rotate_steps in [0, 3] and crop clamped to ints."""
    from Imervue.image.recipe import Recipe

    crop = recipe.crop
    if crop is not None:
        crop = tuple(int(v) for v in crop)  # type: ignore[assignment]
        if crop[2] <= 0 or crop[3] <= 0:
            crop = None
    return Recipe(
        rotate_steps=int(recipe.rotate_steps) % 4,
        flip_h=bool(recipe.flip_h),
        flip_v=bool(recipe.flip_v),
        crop=crop,
        exif_oriented=bool(recipe.exif_oriented),
        brightness=float(recipe.brightness),
        contrast=float(recipe.contrast),
        saturation=float(recipe.saturation),
        exposure=float(recipe.exposure),
        temperature=float(recipe.temperature),
        tint=float(recipe.tint),
        highlights=float(recipe.highlights),
        shadows=float(recipe.shadows),
        whites=float(recipe.whites),
        blacks=float(recipe.blacks),
        vibrance=float(recipe.vibrance),
        tone_curve_rgb=[(float(x), float(y)) for x, y in recipe.tone_curve_rgb],
        tone_curve_r=[(float(x), float(y)) for x, y in recipe.tone_curve_r],
        tone_curve_g=[(float(x), float(y)) for x, y in recipe.tone_curve_g],
        tone_curve_b=[(float(x), float(y)) for x, y in recipe.tone_curve_b],
        lut_path=str(recipe.lut_path or ""),
        lut_intensity=max(0.0, min(1.0, float(recipe.lut_intensity))),
        extra=dict(recipe.extra),
    )
