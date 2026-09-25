"""The one definition of which file extensions Imervue opens."""
from __future__ import annotations

import pytest

from Imervue.image import formats
from Imervue.image.formats import (
    RAW_EXTENSIONS,
    STILL_IMAGE_EXTENSIONS,
    VIEWER_EXTENSIONS,
    ensure_pillow_opener,
)
from Imervue.image.avif_support import AVIF_EXTENSIONS
from Imervue.image.heif_support import HEIF_EXTENSIONS
from Imervue.image.jxl_support import JXL_EXTENSIONS
from Imervue.image.video_frames import VIDEO_EXTENSIONS


def test_sets_nest():
    assert RAW_EXTENSIONS | HEIF_EXTENSIONS | AVIF_EXTENSIONS | JXL_EXTENSIONS <= STILL_IMAGE_EXTENSIONS
    assert VIEWER_EXTENSIONS == STILL_IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    assert not STILL_IMAGE_EXTENSIONS & VIDEO_EXTENSIONS


@pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".jpe", ".jfif", ".jif"])
def test_every_name_a_jpeg_goes_by_opens(ext):
    """Chrome and Edge on Windows save downloads as .jfif, which never showed up."""
    assert ext in formats.JPEG_EXTENSIONS
    assert ext in STILL_IMAGE_EXTENSIONS
    assert ext in formats.RASTER_EXTENSIONS


def test_a_jfif_decodes_and_is_listed(tmp_path):
    from PIL import Image

    from Imervue.gpu_image_view.images.image_loader import _scan_images, decode_image_file
    path = tmp_path / "download.jfif"
    Image.new("RGB", (6, 4), (200, 30, 30)).save(path, format="JPEG")
    assert _scan_images(str(tmp_path)) == [str(path)]
    assert decode_image_file(str(path)).shape == (4, 6, 4)


_EXTRA_SAMPLES = [
    (".ico", "ICO", "RGBA"), (".tga", "TGA", "RGB"), (".dds", "DDS", "RGBA"), (".qoi", "QOI", "RGB"),
    (".jp2", "JPEG2000", "RGB"), (".j2k", "JPEG2000", "RGB"), (".jpf", "JPEG2000", "RGB"),
    (".jpx", "JPEG2000", "RGB"), (".ppm", "PPM", "RGB"), (".pgm", "PPM", "L"), (".pbm", "PPM", "1"),
    (".pnm", "PPM", "RGB"), (".pcx", "PCX", "RGB"),
]


def test_every_extra_format_has_a_sample():
    assert {ext for ext, _fmt, _mode in _EXTRA_SAMPLES} == formats.PILLOW_EXTRA_EXTENSIONS
    assert formats.PILLOW_EXTRA_EXTENSIONS <= STILL_IMAGE_EXTENSIONS


@pytest.mark.parametrize(("ext", "fmt", "mode"), _EXTRA_SAMPLES)
def test_pillows_own_extra_formats_open_for_viewing(tmp_path, ext, fmt, mode):
    """An icon, a texture, a JPEG 2000 scan or a Netpbm frame never showed up."""
    from PIL import Image, features

    from Imervue.gpu_image_view.images.image_loader import _scan_images, decode_image_file
    from Imervue.image.in_place_save import in_place_format
    if fmt == "JPEG2000" and not features.check("jpg_2000"):
        pytest.skip("this Pillow was built without OpenJPEG")
    path = tmp_path / f"picture{ext}"
    Image.new(mode, (32, 32), 1 if mode == "1" else None).save(path, format=fmt)
    assert _scan_images(str(tmp_path)) == [str(path)]
    assert decode_image_file(str(path)).shape == (32, 32, 4)
    assert in_place_format(str(path)) is None   # viewing only: nothing writes it back


def test_rotating_an_extra_format_in_place_is_refused(tmp_path):
    from PIL import Image

    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = tmp_path / "texture.tga"
    Image.new("RGB", (8, 4), (9, 9, 9)).save(path)
    before = path.read_bytes()
    assert lossless_rotate(str(path), clockwise=True) is False
    assert path.read_bytes() == before


def test_extensions_are_lowercase_with_a_dot():
    assert all(e.startswith(".") and e == e.lower() for e in VIEWER_EXTENSIONS)


@pytest.mark.parametrize("ext", [
    ".cr3",     # every Canon body since 2018
    ".rw2", ".nrw", ".pef", ".srw", ".crw", ".3fr", ".iiq",
    ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf",
])
def test_libraw_formats_are_camera_raw(ext):
    """Only six RAW formats used to open: a Canon CR3 or Panasonic RW2 never showed up."""
    assert ext in RAW_EXTENSIONS
    assert ext in VIEWER_EXTENSIONS


@pytest.mark.parametrize("ext", [".x3f", ".raw"])
def test_formats_libraw_cannot_be_trusted_with_are_left_out(ext):
    assert ext not in VIEWER_EXTENSIONS


@pytest.mark.parametrize(("ext", "expected"), [
    (".heic", ["heif"]), (".HEIF", ["heif"]), (".AVIF", []), (".jxl", ["jxl"]),
    (".png", []), (".mp4", []), ("", []),
])
def test_ensure_pillow_opener_registers_only_the_codec_needed(monkeypatch, ext, expected):
    calls = []
    monkeypatch.setattr(formats, "ensure_heif_opener", lambda: calls.append("heif"))
    monkeypatch.setattr(formats, "ensure_jxl_opener", lambda: calls.append("jxl"))
    ensure_pillow_opener(ext)
    assert calls == expected
