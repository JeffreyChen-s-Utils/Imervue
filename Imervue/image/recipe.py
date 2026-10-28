"""Non-destructive edit recipes.

A Recipe describes a series of edits to apply to a source image at load time
without touching the file on disk. The recipe is keyed by ``file_identity``
(first, middle and last 4 KB plus file size, md5'd). Renames preserve it;
metadata rewrites can change the sampled bytes and must carry the recipe over.

Edit order matters and is fixed:

    1.  Rotate (quarter turns)
    2.  Flip horizontal
    3.  Flip vertical
    4.  Crop (in post-rotate/flip coordinates)
    5.  White balance (temperature + tint)
    6.  Exposure (multiplicative)
    7.  Highlights / Shadows (luminance-weighted gain)
    8.  Whites / Blacks (endpoint remap)
    9.  Brightness
    10. Contrast
    11. Vibrance (saturation-protected colour boost)
    12. Saturation

This order is baked into ``apply()`` and callers must not reorder without
also updating the hash scheme — otherwise two recipes that produce the same
pixels but were constructed in different orders would collide on cache lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

import numpy as np

from Imervue.image.recipe_identity import RecipeIdentity
from Imervue.image.recipe_codec import RecipeCodec
from Imervue.image.recipe_values import normalized
from Imervue.image.recipe_geometry import (
    _apply_geometry,
    turned_with_file,
)
from Imervue.image.recipe_file_identity import (
    file_identities,
    file_identity,
    clear_identity_cache,
)
from Imervue.image.recipe_pixels import (
    _apply_white_balance,
    _apply_highlights_shadows,
    _apply_whites_blacks,
    _apply_vibrance,
    _apply_tone_curve,
    _apply_exposure,
    _apply_brightness_contrast,
    _apply_saturation,
)
from Imervue.image.recipe_optional_effects import (
    _apply_levels,
    _apply_channel_mixer,
    _apply_gradient_map,
    _apply_lens_flare,
    _apply_film_grain,
)
from Imervue.image.recipe_color_effects import (
    _apply_split_toning,
    _apply_lut,
    _apply_threshold_posterize,
)
from Imervue.image.recipe_compositing import (
    _apply_layer_stack,
    _apply_masks,
)


__all__ = ["Recipe", "STAGE_NAMES", "file_identities", "file_identity",
           "clear_identity_cache", "turned_with_file"]


@dataclass
class Recipe(RecipeIdentity, RecipeCodec):
    """Non-destructive edit recipe for a single image.

    All fields default to the identity transform — a default-constructed
    Recipe is a no-op and ``is_identity()`` returns True. Numeric adjustments
    are in ``[-1.0, +1.0]`` where 0 = no change; exposure is ``[-2.0, +2.0]``
    stops so callers can brighten dark RAW files properly.
    """

    rotate_steps: int = 0  # 0, 1, 2, 3 = 0°, 90°, 180°, 270° CW
    flip_h: bool = False
    flip_v: bool = False
    crop: tuple[int, int, int, int] | None = None  # (x, y, w, h) post-rotate
    # Whether the geometry above was set on the EXIF-upright image. Images load
    # upright now; a recipe saved before that (no such key, see ``from_dict``)
    # set its rotate / flip / crop on the sideways pixels, so those keep them.
    exif_oriented: bool = True
    brightness: float = 0.0  # -1..+1
    contrast: float = 0.0  # -1..+1
    saturation: float = 0.0  # -1..+1
    exposure: float = 0.0  # -2..+2 (stops)
    # Advanced develop sliders (flag-based). All -1..+1 and default to
    # zero so existing recipes deserialise unchanged (see `from_dict`).
    temperature: float = 0.0  # warm (+) / cool (-) white balance
    tint: float = 0.0  # magenta (+) / green (-)
    highlights: float = 0.0  # recover bright areas (negative darkens)
    shadows: float = 0.0  # lift dark areas (positive brightens)
    whites: float = 0.0  # endpoint stretch on the bright side
    blacks: float = 0.0  # endpoint crush on the dark side
    vibrance: float = 0.0  # saturation-protected colour boost

    # Tone curves — lists of (input, output) points in [0, 1]. Empty = identity.
    tone_curve_rgb: list[tuple[float, float]] = field(default_factory=list)
    tone_curve_r: list[tuple[float, float]] = field(default_factory=list)
    tone_curve_g: list[tuple[float, float]] = field(default_factory=list)
    tone_curve_b: list[tuple[float, float]] = field(default_factory=list)

    # .cube LUT path — applied after tone curves. Empty = disabled.
    lut_path: str = ""
    lut_intensity: float = 1.0  # 0..1 blend between original and LUT

    # Freeform metadata for forward-compat — callers may stuff additional
    # fields here (e.g. develop panel version) and they round-trip through
    # save/load without the core code having to know about them.
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------

    def normalized(self) -> Recipe:
        """Return a copy with rotate_steps in [0, 3] and crop clamped to ints."""
        return normalized(self)

    def apply(self, arr: np.ndarray) -> np.ndarray:
        """Apply this recipe to an RGBA numpy array without modifying the input.

        Identity recipes return the input object without validation. Otherwise
        input must be HxWx4 and is converted to uint8 before rendering.
        """
        if self.is_identity():
            return arr

        if arr.ndim != 3 or arr.shape[2] != 4:
            raise ValueError(f"Recipe.apply expects HxWx4 RGBA, got shape={arr.shape}")
        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)

        return self.normalized().apply_stages(arr)

    def apply_stages(
        self, arr: np.ndarray, first: str | None = None, last: str | None = None
    ) -> np.ndarray:
        """Run the stages of :data:`STAGE_NAMES` from *first* to *last* (inclusive) on *arr*.

        ``apply`` runs them all on the normalised recipe; a renderer that does
        some stages itself runs the others through here. *arr* must already be
        HxWx4 uint8, and the recipe normalised.
        """
        start = 0 if first is None else STAGE_NAMES.index(first)
        stop = len(_STAGES) if last is None else STAGE_NAMES.index(last) + 1
        for _name, stage in _STAGES[start:stop]:
            arr = stage(arr, self)
        return arr


# The develop pipeline, in order: each stage takes and returns an HxWx4 uint8
# array and passes it through unchanged when its settings are neutral.
_STAGES: tuple[tuple[str, Callable[[np.ndarray, Recipe], np.ndarray]], ...] = (
    ("geometry", _apply_geometry),
    ("white_balance", _apply_white_balance),
    ("exposure", _apply_exposure),
    ("highlights_shadows", _apply_highlights_shadows),
    ("whites_blacks", _apply_whites_blacks),
    ("brightness_contrast", _apply_brightness_contrast),
    ("vibrance", _apply_vibrance),
    ("saturation", _apply_saturation),
    ("tone_curve", _apply_tone_curve),
    ("split_toning", _apply_split_toning),
    ("lut", _apply_lut),
    ("masks", _apply_masks),
    ("levels", _apply_levels),
    ("channel_mixer", _apply_channel_mixer),
    ("gradient_map", _apply_gradient_map),
    ("threshold_posterize", _apply_threshold_posterize),
    ("lens_flare", _apply_lens_flare),
    ("film_grain", _apply_film_grain),
    ("layer_stack", _apply_layer_stack),
)
#: Names of the develop stages in the order ``Recipe.apply`` runs them.
STAGE_NAMES: tuple[str, ...] = tuple(name for name, _stage in _STAGES)
