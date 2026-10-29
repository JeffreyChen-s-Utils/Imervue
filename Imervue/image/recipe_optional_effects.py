"""Optional decoded effects: import failure skips, decode errors propagate, apply errors warn."""

from __future__ import annotations

import logging
from functools import partial

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


logger = logging.getLogger("Imervue.recipe")


def _load_levels():
    from Imervue.image.levels import LevelsOptions, apply_levels

    return LevelsOptions, apply_levels


def _load_channel_mixer():
    from Imervue.image.channel_mixer import ChannelMixerOptions, apply_channel_mixer

    return ChannelMixerOptions, apply_channel_mixer


def _load_gradient_map():
    from Imervue.image.gradient_map import GradientMapOptions, apply_gradient_map

    return GradientMapOptions, apply_gradient_map


def _load_lens_flare():
    from Imervue.image.lens_flare import LensFlareOptions, apply_lens_flare

    return LensFlareOptions, apply_lens_flare


def _load_film_grain():
    from Imervue.image.film_grain import FilmGrainOptions, apply_film_grain

    return FilmGrainOptions, apply_film_grain


def _apply_optional(arr: np.ndarray, recipe: Recipe, *, key, load, label) -> np.ndarray:
    if not recipe.extra:
        return arr
    try:
        options_type, apply = load()
    except ImportError:
        return arr
    options = options_type.from_dict(recipe.extra.get(key))
    try:
        return apply(arr, options)
    except (ValueError, TypeError) as err:
        logger.warning("%s apply failed: %s", label, err)
        return arr


_apply_levels = partial(_apply_optional, key="levels", load=_load_levels, label="Levels")
_apply_channel_mixer = partial(
    _apply_optional, key="channel_mixer", load=_load_channel_mixer, label="Channel mixer"
)
_apply_gradient_map = partial(
    _apply_optional, key="gradient_map", load=_load_gradient_map, label="Gradient map"
)
_apply_lens_flare = partial(
    _apply_optional, key="lens_flare", load=_load_lens_flare, label="Lens flare"
)
_apply_film_grain = partial(
    _apply_optional, key="film_grain", load=_load_film_grain, label="Film grain"
)
