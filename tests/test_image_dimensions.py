"""Header-only pixel dimensions: libraw for RAW, Pillow (with its optional codecs) for the rest."""
from __future__ import annotations

import pytest
from PIL import Image

from Imervue.image import dimensions
from Imervue.image.dimensions import image_dimensions


def test_raster_size_comes_from_the_header(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (37, 21)).save(path)
    assert image_dimensions(path) == (37, 21)


def test_raw_goes_to_libraw_not_pillow(tmp_path, monkeypatch):
    """Pillow opens a CR2 as TIFF and reports its embedded preview's size."""
    seen = []
    monkeypatch.setattr(dimensions, "raw_dimensions", lambda p: seen.append(p) or (6000, 4000))
    path = tmp_path / "a.CR2"
    Image.new("RGB", (160, 120)).save(path, format="TIFF")   # what Pillow would see
    assert image_dimensions(path) == (6000, 4000)
    assert seen == [path]


@pytest.mark.parametrize("name", ["missing.png", "missing.cr2"])
def test_missing_file_is_none(tmp_path, name):
    assert image_dimensions(tmp_path / name) is None


def test_undecodable_file_is_none(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    assert image_dimensions(bad) is None


def test_heic_size_is_read(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    path = tmp_path / "a.heic"
    Image.new("RGB", (48, 32)).save(path)
    assert image_dimensions(path) == (48, 32)


def test_codec_is_registered_before_reading(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(dimensions, "ensure_pillow_opener", seen.append)
    image_dimensions(tmp_path / "a.JXL")
    assert seen == [".jxl"]


def test_quarter_turn_orientation_reports_the_upright_size(tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    assert image_dimensions(path) == (20, 40)
