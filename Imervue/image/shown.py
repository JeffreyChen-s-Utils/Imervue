"""An image as the viewer shows it: colour-managed to sRGB, then turned upright.

Every place that decodes a file itself (previews, tool inputs, exports) goes
through :func:`as_shown` so it agrees with the viewer. Its output carries
neither an orientation tag nor a colour profile, which is exactly right for a
copy that is saved without EXIF or ICC.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.image.color_profile import to_srgb
from Imervue.image.formats import ensure_pillow_opener
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


def _load_shown(path, mode: str) -> np.ndarray:
    ensure_pillow_opener(Path(path).suffix.lower())
    with Image.open(path) as img:
        return np.array(as_shown(img).convert(mode), dtype=np.uint8)


def load_shown_rgb(path) -> np.ndarray:
    """Load *path* as an HxWx3 uint8 RGB array, as the viewer shows it (HEIC / JXL too)."""
    return _load_shown(path, "RGB")


def load_shown_rgba(path) -> np.ndarray:
    """Load *path* as an HxWx4 uint8 RGBA array, as the viewer shows it (HEIC / JXL too)."""
    return _load_shown(path, "RGBA")
