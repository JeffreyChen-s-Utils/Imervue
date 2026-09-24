"""Open an image the way the viewer shows it, as the source of an exported file.

The exporters write the new file without an ICC profile or orientation tag
(its EXIF is only what ``export_metadata`` lets through), so anything the viewer
takes from the file's metadata has to be baked into the pixels here: the EXIF
orientation, the colour profile and the non-destructive Develop recipe. Camera
RAW is developed at full size and SVG rasterised, through the viewer's decode.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store


def recipe_base_image(path: str, recipe: Recipe | None) -> Image.Image:
    """Return the pixels *recipe* applies to: *path* upright, as the viewer loads it.

    Converted to sRGB from an embedded colour profile, like the viewer. The
    exception to the turn is a recipe whose geometry predates EXIF-upright loading
    (``Recipe.base_is_oriented``): its rotate / flip / crop was drawn on the
    stored orientation, so that is what it gets. Anything that stores
    coordinates in a recipe (a crop, face boxes) must compute them on this image.
    """
    from Imervue.gpu_image_view.images.image_loader import decode_image_file
    # The viewer's decode: RAW developed at full size (Pillow alone reads its small
    # embedded preview), SVG rasterised, sRGB always.
    orient = recipe is None or recipe.base_is_oriented()
    return Image.fromarray(decode_image_file(path, orient=orient), "RGBA")


def open_export_source(path: str) -> Image.Image:
    """Return *path* upright, with its Develop recipe applied, ready to be saved elsewhere."""
    recipe = recipe_store.get_for_path(path)
    img = recipe_base_image(path, recipe)
    if recipe is not None and not recipe.is_identity():
        img = Image.fromarray(recipe.apply(np.array(img)))
    return img
