"""An image as the viewer shows it: colour-managed to sRGB, then turned upright.

Every place that decodes a file itself (previews, tool inputs, exports) goes
through :func:`as_shown` so it agrees with the viewer. Its output carries
neither an orientation tag nor a colour profile, which is exactly right for a
copy that is saved without EXIF or ICC; it keeps the file's bit depth. What
goes to the screen takes :func:`as_shown_8bit`, which scales 16-bit and float
grey instead of letting ``convert`` clip it. :func:`open_shown` decodes a
whole file that way, camera RAW included, without Qt.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.image.color_profile import to_srgb
from Imervue.image.formats import RAW_EXTENSIONS, ensure_pillow_opener
from Imervue.image.high_bit_depth import to_eight_bit
from Imervue.image.orientation import exif_orientation, transpose_for
from Imervue.image.raw_loader import develop_raw


def as_shown(img: Image.Image, code: int | None = None) -> Image.Image:
    """Return *img* converted to sRGB and turned upright.

    Pass *code* when the orientation was read before an in-place step that
    loses it (``thumbnail`` keeps it, but a caller may have converted first).
    It must come from the original image: the sRGB conversion drops EXIF.
    """
    if code is None:
        code = exif_orientation(img)
    return transpose_for(to_srgb(img), code)


def as_shown_8bit(img: Image.Image, code: int | None = None, mode: str = "RGBA") -> Image.Image:
    """:func:`as_shown` in 8-bit *mode*, the pixels the screen gets.

    A 16-bit or floating-point grey picture is scaled over its range first
    (:func:`~Imervue.image.high_bit_depth.to_eight_bit`): a plain ``convert``
    clips it, and a 16-bit greyscale scan showed almost white.
    """
    return to_eight_bit(as_shown(img, code)).convert(mode)


def open_shown(path: str | Path) -> Image.Image:
    """Decode *path* as the viewer shows it; the file is closed on return.

    A camera RAW is developed through libraw like the viewer does: Pillow
    would return its embedded preview (a NEF's is 160×120) or nothing at all
    (CR3, RW2). Anything else is converted to sRGB and turned upright, HEIC /
    JPEG XL with their codec registered. Raises ``IMAGE_READ_ERRORS``.
    """
    ext = Path(path).suffix.lower()
    if ext in RAW_EXTENSIONS:
        return Image.fromarray(develop_raw(path))
    ensure_pillow_opener(ext)
    with Image.open(path) as img:
        img.load()
        shown = as_shown(img)
        return shown if shown is not img else img.copy()


def _load_shown(path, mode: str) -> np.ndarray:
    return np.array(to_eight_bit(open_shown(path)).convert(mode), dtype=np.uint8)


def load_shown_rgb(path) -> np.ndarray:
    """Load *path* as an HxWx3 uint8 RGB array, as the viewer shows it (RAW, HEIC, JXL too)."""
    return _load_shown(path, "RGB")


def load_shown_rgba(path) -> np.ndarray:
    """Load *path* as an HxWx4 uint8 RGBA array, as the viewer shows it (RAW, HEIC, JXL too)."""
    return _load_shown(path, "RGBA")
