"""Open an image the way the viewer shows it, as the source of an exported file.

The exporters write the new file without EXIF, so anything the viewer takes
from the metadata has to be baked into the pixels here: the EXIF orientation,
and the non-destructive Develop recipe. SVG is rasterised.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.image.orientation import exif_orientation, transpose_for
from Imervue.image.recipe_store import recipe_store


def open_export_source(path: str) -> Image.Image:
    """Return *path* upright, with its Develop recipe applied, ready to be saved elsewhere.

    A recipe whose geometry predates EXIF-upright loading (``Recipe.base_is_oriented``)
    is applied to the stored orientation, as the viewer applies it.
    """
    recipe = recipe_store.get_for_path(path)
    if Path(path).suffix.lower() == ".svg":
        from Imervue.gpu_image_view.images.image_loader import _load_svg
        img = Image.fromarray(_load_svg(path, thumbnail=False))
    else:
        img = Image.open(path)
        if recipe is None or recipe.base_is_oriented():
            img = transpose_for(img, exif_orientation(img))
    if recipe is not None and not recipe.is_identity():
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img = Image.fromarray(recipe.apply(np.array(img)))
    return img
