"""Recipe geometry and following a physical file rotation."""

from __future__ import annotations

from dataclasses import replace

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


def _apply_geometry(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Rotate / flip / crop — steps 1-4 of the pipeline."""
    if recipe.rotate_steps:
        arr = np.ascontiguousarray(np.rot90(arr, k=-recipe.rotate_steps))
    if recipe.flip_h:
        arr = np.ascontiguousarray(arr[:, ::-1])
    if recipe.flip_v:
        arr = np.ascontiguousarray(arr[::-1, :])
    if recipe.crop is not None:
        h, w = arr.shape[:2]
        cx, cy, cw, ch = recipe.crop
        x0 = max(0, min(cx, w))
        y0 = max(0, min(cy, h))
        x1 = max(x0, min(cx + cw, w))
        y1 = max(y0, min(cy + ch, h))
        if x1 > x0 and y1 > y0:
            arr = np.ascontiguousarray(arr[y0:y1, x0:x1])
    return arr


_POSITIONED_EXTRAS = ("masks", "layers", "lens_flare", "face_tags")


def turned_with_file(recipe: Recipe, *, clockwise: bool, size: tuple[int, int]) -> Recipe | None:
    """*recipe* for the photo after its file turned a quarter; *size* = upright size before.

    The new result is the old one turned the same way: the recipe's own
    rotation stays, the flips trade axes and the crop box turns within the
    rotated frame. ``None`` when the recipe can't follow: it was set on the
    sideways pixels (``exif_oriented`` False), or it holds masks, layers, a
    lens flare or face tags, whose positions would all need moving.
    """
    if not recipe.exif_oriented or any(recipe.extra.get(key) for key in _POSITIONED_EXTRAS):
        return None
    width, height = size
    if recipe.rotate_steps % 2:
        width, height = height, width  # the frame the crop is measured in
    crop = recipe.crop
    if crop is not None:
        x, y, w, h = crop
        crop = (height - y - h, x, h, w) if clockwise else (y, width - x - w, h, w)
    return replace(  # NOSONAR  # dataclasses.replace returns the Recipe it copies
        recipe, flip_h=recipe.flip_v, flip_v=recipe.flip_h, crop=crop
    )
