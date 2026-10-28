"""Neutral-value predicates shared by recipe evaluation and pixel stages."""

from __future__ import annotations

from Imervue.image.tone_curve import is_identity_points
from Imervue.image.recipe_values import (
    ADVANCED_SLIDERS, CLASSIC_SLIDERS, CURVES, extra_is_identity, _is_zero,
)


class RecipeIdentity:
    def is_identity(self) -> bool:
        return (
            self._geometry_is_identity()
            and self._classic_sliders_are_zero()
            and self._advanced_sliders_are_zero()
            and self._curves_are_identity()
            and not self.lut_path
            and self._extra_is_identity()
        )

    def _extra_is_identity(self) -> bool:
        return extra_is_identity(self.extra)

    def _curves_are_identity(self) -> bool:
        return all(is_identity_points(getattr(self, key)) for key in CURVES)

    def base_is_oriented(self) -> bool:
        """Whether this recipe applies to the EXIF-upright image.

        True unless it is a recipe saved before images loaded upright AND it
        carries geometry; tone-only edits don't depend on the orientation.
        """
        return self.exif_oriented or self._geometry_is_identity()

    def _geometry_is_identity(self) -> bool:
        return (
            self.rotate_steps % 4 == 0 and not self.flip_h and not self.flip_v and self.crop is None
        )

    def _classic_sliders_are_zero(self) -> bool:
        return all(_is_zero(getattr(self, key)) for key in CLASSIC_SLIDERS)

    def _advanced_sliders_are_zero(self) -> bool:
        return all(_is_zero(getattr(self, key)) for key in ADVANCED_SLIDERS)
