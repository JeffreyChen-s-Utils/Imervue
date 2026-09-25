"""``as_shown``: sRGB first (from the original's profile), then the EXIF turn."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from _icc_profiles import DISPLAY_P3
from PIL import Image

from Imervue.image import shown as shown_module
from Imervue.image.color_profile import to_srgb
from Imervue.image.shown import as_shown, load_shown_rgb, load_shown_rgba, open_shown

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


# ---------------------------------------------------------------------------
# open_shown: camera RAW developed, not its embedded preview
# ---------------------------------------------------------------------------


def _preview_only_nef(tmp_path, name="shot.nef"):
    """A file Pillow opens as the 160x120 thumbnail a NEF keeps in IFD0."""
    path = tmp_path / name
    Image.new("RGB", (160, 120), (0, 0, 255)).save(path, format="TIFF")
    return path


def _develops(monkeypatch, shape=(300, 450, 3)):
    seen = []
    developed = np.full(shape, 90, dtype=np.uint8)

    def develop(path, thumbnail=False):
        seen.append((Path(path).name, thumbnail))
        return developed
    monkeypatch.setattr(shown_module, "develop_raw", develop)
    return seen


def test_a_raw_is_developed_not_read_as_its_preview(tmp_path, monkeypatch):
    """HDR merge, panorama and focus stack read a NEF as its 160x120 thumbnail."""
    seen = _develops(monkeypatch)
    assert load_shown_rgb(_preview_only_nef(tmp_path)).shape == (300, 450, 3)
    rgba = load_shown_rgba(_preview_only_nef(tmp_path, "IMG_1.CR3"))
    assert rgba.shape == (300, 450, 4)
    assert (rgba[..., 3] == 255).all()
    assert seen == [("shot.nef", False), ("IMG_1.CR3", False)]


@pytest.mark.parametrize(("module", "loader"), [
    ("Imervue.image.hdr_merge", "_load_bgr"),
    ("Imervue.image.panorama", "_load_bgr"),
    ("Imervue.image.focus_stack", "_load_rgb"),
    ("Imervue.image.stack_blend", "_load_rgb"),
])
def test_multi_image_tools_develop_raw_brackets(tmp_path, monkeypatch, module, loader):
    import importlib
    _develops(monkeypatch, shape=(30, 45, 3))
    load = getattr(importlib.import_module(module), loader)
    assert load(_preview_only_nef(tmp_path, "bracket.CR2")).shape == (30, 45, 3)


def test_an_unreadable_raw_is_an_image_read_error(tmp_path):
    from Imervue.image.read_errors import IMAGE_READ_ERRORS
    path = tmp_path / "broken.nef"
    path.write_bytes(b"not a raw file" * 20)
    with pytest.raises(IMAGE_READ_ERRORS):
        open_shown(path)


def test_open_shown_leaves_the_file_closed_and_the_pixels_loaded(tmp_path):
    path = tmp_path / "plain.png"
    Image.new("RGB", (6, 4), (10, 20, 30)).save(path)
    img = open_shown(path)
    path.unlink()                     # Windows refuses while a handle is open
    assert img.size == (6, 4)
    assert img.getpixel((0, 0)) == (10, 20, 30)


def test_open_shown_turns_and_converts(tmp_path):
    img = open_shown(_tagged_p3_portrait(tmp_path))
    assert img.size == (20, 40)
    assert np.abs(np.array(img.getpixel((10, 20))) - _srgb_red()).max() <= 3
