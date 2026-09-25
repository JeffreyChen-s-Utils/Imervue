"""Embedded colour profiles are converted to sRGB; untagged and sRGB images pass through."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from _icc_profiles import DISPLAY_P3, grey_profile
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


@pytest.mark.parametrize("mode", ["P", "1", "I"])
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
    assert color_profile._transform.cache_info().hits >= 1  # pylint: disable=no-value-for-parameter


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


_GAMMA_18 = grey_profile(1.8, "Gray Gamma 1.8")
_MID_GREY_IN_SRGB = 146   # level 128 of a gamma-1.8 grey, as sRGB shows it


def _grey_image(mode="L", level=128):
    img = Image.new(mode, (4, 4), level if mode == "L" else (level, 77))
    img.info["icc_profile"] = _GAMMA_18
    return img


def test_a_grey_profile_is_applied_and_the_picture_stays_grey():
    """A Photoshop grey image's midtones showed as their stored numbers."""
    out = to_srgb(_grey_image())
    assert out.mode == "L"
    assert abs(out.getpixel((0, 0)) - _MID_GREY_IN_SRGB) <= 1
    assert "icc_profile" not in out.info


@pytest.mark.parametrize("level", [0, 255])
def test_black_and_white_stay_black_and_white(level):
    assert to_srgb(_grey_image(level=level)).getpixel((0, 0)) == level


def test_grey_alpha_survives_the_conversion():
    out = to_srgb(_grey_image("LA"))
    assert out.mode == "LA"
    level, alpha = out.getpixel((0, 0))
    assert abs(level - _MID_GREY_IN_SRGB) <= 1
    assert alpha == 77


@pytest.mark.parametrize("mode", ["L", "LA"])
def test_a_grey_image_with_a_colour_profile_shows_the_stored_levels(mode):
    img = Image.new(mode, (2, 2))
    img.info["icc_profile"] = DISPLAY_P3   # an RGB profile can't describe grey levels
    assert to_srgb(img) is img


def test_a_colour_image_with_a_grey_profile_shows_the_stored_pixels():
    img = Image.new("RGB", (2, 2), _P3_RED)
    img.info["icc_profile"] = _GAMMA_18
    assert to_srgb(img) is img


def test_grey_curves_are_built_once_per_profile():
    color_profile._grey_curve.cache_clear()
    to_srgb(_grey_image())
    to_srgb(_grey_image("LA"))
    assert color_profile._grey_curve.cache_info().hits >= 1  # pylint: disable=no-value-for-parameter


@pytest.mark.parametrize("suffix", [".jpg", ".png"])
def test_viewer_and_thumbnail_loads_apply_a_grey_profile(tmp_path, suffix):
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
    path = tmp_path / f"scan{suffix}"
    Image.new("L", (16, 16), 128).save(path, icc_profile=_GAMMA_18)
    for arr in (load_image_file(str(path)), load_image_file(str(path), thumbnail=True),
                LoadThumbnailWorker(str(path), size=8)._bake_fresh(None, "")):
        assert np.abs(arr[1, 1, :3].astype(int) - _MID_GREY_IN_SRGB).max() <= 2


def test_a_sixteen_bit_grey_scan_keeps_its_profile_through_the_scaling(tmp_path):
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    path = tmp_path / "scan16.png"
    Image.new("I;16", (8, 8), 32896).save(path, icc_profile=_GAMMA_18)   # 128 in 8 bits
    arr = load_image_file(str(path))
    assert np.abs(arr[1, 1, :3].astype(int) - _MID_GREY_IN_SRGB).max() <= 2
