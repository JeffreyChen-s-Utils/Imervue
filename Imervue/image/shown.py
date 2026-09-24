"""An image as the viewer shows it: colour-managed to sRGB, then turned upright.

Every place that decodes a file itself (previews, tool inputs, exports) goes
through :func:`as_shown` so it agrees with the viewer. Its output carries
neither an orientation tag nor a colour profile, which is exactly right for a
copy that is saved without EXIF or ICC.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.image.color_profile import to_srgb
from Imervue.image.orientation import exif_orientation, transpose_for


def as_shown(img: Image.Image, code: int | None = None) -> Image.Image:
    """Return *img* converted to sRGB and turned upright.

    Pass *code* when the orientation was read before an in-place step that
    loses it (``thumbnail`` keeps it, but a caller may have converted first).
    It must come from the original image: the sRGB conversion drops EXIF.
    """
    if code is None:
        code = exif_orientation(img)
    return transpose_for(to_srgb(img), code)


def load_shown_rgb(path) -> np.ndarray:
    """Load *path* as an HxWx3 uint8 RGB array, as the viewer shows it."""
    with Image.open(path) as img:
        return np.asarray(as_shown(img).convert("RGB"), dtype=np.uint8)
