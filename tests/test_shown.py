"""``as_shown``: sRGB first (from the original's profile), then the EXIF turn."""
from __future__ import annotations

import numpy as np
from _icc_profiles import DISPLAY_P3
from PIL import Image

from Imervue.image.color_profile import to_srgb
from Imervue.image.shown import as_shown, load_shown_rgb

_P3_RED = (200, 60, 50)


def _tagged_p3_portrait(tmp_path):
    """40x20 stored, Display P3, tagged 6: shown 20x40 in sRGB."""
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "p.jpg"
    Image.new("RGB", (40, 20), _P3_RED).save(path, exif=exif, icc_profile=DISPLAY_P3, quality=100)
    return str(path)


def _srgb_red():
    img = Image.new("RGB", (1, 1), _P3_RED)
    img.info["icc_profile"] = DISPLAY_P3
    return np.array(to_srgb(img).getpixel((0, 0)))


def test_as_shown_converts_colour_and_turns(tmp_path):
    """The sRGB conversion drops EXIF, so the orientation is read from the original first."""
    with Image.open(_tagged_p3_portrait(tmp_path)) as img:
        shown = as_shown(img)
    assert shown.size == (20, 40)
    assert "icc_profile" not in shown.info
    assert np.abs(np.array(shown.getpixel((10, 20))) - _srgb_red()).max() <= 3


def test_explicit_code_overrides_the_tag(tmp_path):
    with Image.open(_tagged_p3_portrait(tmp_path)) as img:
        assert as_shown(img, 1).size == (40, 20)


def test_untagged_srgb_image_is_returned_as_is():
    img = Image.new("RGB", (3, 2))
    assert as_shown(img) is img


def test_load_shown_rgb(tmp_path):
    arr = load_shown_rgb(_tagged_p3_portrait(tmp_path))
    assert arr.shape == (40, 20, 3) and arr.dtype == np.uint8
    assert np.abs(arr[20, 10].astype(int) - _srgb_red()).max() <= 3


def test_tool_loader_and_export_base_are_colour_managed(tmp_path):
    """Tools and exports save without ICC; unconverted pixels changed colour on the way out."""
    from Imervue.gui._apply_save import load_rgba
    from Imervue.gui.export_source import recipe_base_image
    path = _tagged_p3_portrait(tmp_path)
    tool = load_rgba(path)
    assert tool.shape == (40, 20, 4)
    assert np.abs(tool[20, 10, :3].astype(int) - _srgb_red()).max() <= 3
    base = recipe_base_image(path, None)
    assert np.abs(np.array(base.getpixel((10, 20)))[:3] - _srgb_red()).max() <= 3
