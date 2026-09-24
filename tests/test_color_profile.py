"""Embedded colour profiles are converted to sRGB; untagged and sRGB images pass through."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from _icc_profiles import DISPLAY_P3
from PIL import Image, ImageCms

from Imervue.image import color_profile
from Imervue.image.color_profile import to_srgb

_P3_RED = (200, 60, 50)   # a saturated red that sRGB shows more intense


def _p3_image(mode="RGB", colour=_P3_RED):
    img = Image.new(mode, (4, 4), colour if mode == "RGB" else (*colour, 128))
    img.info["icc_profile"] = DISPLAY_P3
    return img


def test_display_p3_pixels_are_converted():
    out = to_srgb(_p3_image())
    red, green, blue = out.getpixel((0, 0))
    assert red > _P3_RED[0] + 5 and green < _P3_RED[1]   # the wider-gamut red, in sRGB numbers
    assert "icc_profile" not in out.info                  # converted once, never again


def test_alpha_survives_the_conversion():
    out = to_srgb(_p3_image("RGBA"))
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 128


def test_untagged_image_is_returned_untouched():
    img = Image.new("RGB", (2, 2), _P3_RED)
    assert to_srgb(img) is img


def test_srgb_tagged_image_is_returned_untouched():
    img = Image.new("RGB", (2, 2), _P3_RED)
    img.info["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    assert to_srgb(img) is img


@pytest.mark.parametrize("mode", ["L", "P", "LA"])
def test_modes_without_a_conversion_are_returned_untouched(mode):
    img = Image.new(mode, (2, 2))
    img.info["icc_profile"] = DISPLAY_P3
    assert to_srgb(img) is img


def test_a_corrupt_profile_shows_the_stored_pixels(caplog):
    img = Image.new("RGB", (2, 2), _P3_RED)
    img.info["icc_profile"] = b"not an icc profile"
    with caplog.at_level("DEBUG", logger="Imervue.color_profile"):
        assert to_srgb(img) is img
    assert "Unusable embedded colour profile" in caplog.text


def test_transforms_are_built_once_per_profile_and_mode():
    color_profile._transform.cache_clear()
    to_srgb(_p3_image())
    to_srgb(_p3_image())
    assert color_profile._transform.cache_info().hits >= 1


_WINDOWS_CMYK = Path(r"C:\Windows\System32\spool\drivers\color\RSWOP.icm")


@pytest.mark.skipif(not _WINDOWS_CMYK.is_file(), reason="needs the Windows SWOP CMYK profile")
def test_cmyk_with_a_profile_becomes_rgb():
    img = Image.new("CMYK", (2, 2), (0, 255, 255, 0))   # full magenta + yellow: red
    img.info["icc_profile"] = _WINDOWS_CMYK.read_bytes()
    out = to_srgb(img)
    assert out.mode == "RGB"
    red, green, blue = out.getpixel((0, 0))
    assert red > 150 and green < 120 and blue < 120


def test_viewer_and_thumbnail_loads_are_colour_managed(tmp_path):
    """The viewer showed a Display P3 photo's numbers as if they were sRGB."""
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
    path = tmp_path / "p3.png"
    Image.new("RGB", (8, 8), _P3_RED).save(path, icc_profile=DISPLAY_P3)
    expected = np.array(to_srgb(_p3_image()).getpixel((0, 0)))
    for arr in (load_image_file(str(path)), load_image_file(str(path), thumbnail=True),
                LoadThumbnailWorker(str(path), size=4)._bake_fresh(None, "")):
        assert np.abs(arr[1, 1, :3].astype(int) - expected).max() <= 2
