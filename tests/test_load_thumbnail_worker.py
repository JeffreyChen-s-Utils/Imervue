"""Tests for ``LoadThumbnailWorker``: RAW through raw_loader's upright preview, EXIF-upright rasters."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.gpu_image_view.images import load_thumbnail_worker as mod
from Imervue.image import raw_loader


def _developed(monkeypatch, shape):
    calls = []

    def develop(path, thumbnail=False):
        calls.append((path, thumbnail))
        return np.full(shape, 200, dtype=np.uint8)
    monkeypatch.setattr(raw_loader, "develop_raw", develop)
    return calls


@pytest.mark.parametrize(("size", "shape"), [(None, (1500, 1000, 3)), (64, (64, 43, 4))])
def test_a_raw_thumbnail_is_raw_loaders_upright_preview(monkeypatch, size, shape):
    """The worker had its own libraw path that never turned a portrait preview upright."""
    calls = _developed(monkeypatch, (1500, 1000, 3))
    data = mod.LoadThumbnailWorker("shot.cr3", size=size)._load_raw()  # noqa: SLF001
    assert calls == [("shot.cr3", True)]
    assert data.shape == shape


def test_a_large_raw_preview_is_capped_at_2048(monkeypatch):
    _developed(monkeypatch, (4000, 6000, 3))
    data = mod.LoadThumbnailWorker("shot.nef", size=None)._load_raw()  # noqa: SLF001
    assert 2040 <= max(data.shape[:2]) <= 2048   # int() of the scaled sides


def test_an_unreadable_raw_is_an_image_read_error(tmp_path):
    from Imervue.image.read_errors import IMAGE_READ_ERRORS
    path = tmp_path / "broken.cr2"
    path.write_bytes(b"not a raw file" * 20)
    with pytest.raises(IMAGE_READ_ERRORS):
        mod.LoadThumbnailWorker(str(path), size=64)._load_raw()  # noqa: SLF001


def _portrait(tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return str(path)


@pytest.mark.parametrize("size", [None, 16])
def test_tagged_photo_thumbnail_is_upright(tmp_path, size):
    worker = mod.LoadThumbnailWorker(_portrait(tmp_path), size=size)
    arr = worker._bake_fresh(None, "")
    height, width = arr.shape[:2]
    assert height > width


def test_legacy_geometry_recipe_keeps_the_stored_orientation(tmp_path):
    from Imervue.image.recipe import Recipe
    worker = mod.LoadThumbnailWorker(_portrait(tmp_path), size=None)
    arr = worker._bake_fresh(Recipe.from_dict({"rotate_steps": 2}), "x")
    assert arr.shape[:2] == (20, 40)   # rotated 180 on the stored 40x20 pixels



@pytest.mark.parametrize("size", [None, 64])
def test_a_sixteen_bit_grey_tile_shows_its_gradient(tmp_path, size):
    path = tmp_path / "depth.png"
    Image.fromarray(np.tile(np.linspace(0, 65535, 128).astype(np.uint16), (4, 1))).save(path)
    row = mod.LoadThumbnailWorker(str(path), size=size)._bake_fresh(None, "")[0, :, 0].astype(int)
    assert row[0] <= 2          # a downscale averages the first pixels with their neighbours
    assert row[-1] >= 253
    assert abs(row[len(row) // 2] - 128) <= 3   # it was nearly all 255: clipped, not scaled


@pytest.mark.parametrize("size", [None, 64])
def test_a_tile_decodes_in_the_giant_decode_slot(tmp_path, monkeypatch, size):
    from contextlib import contextmanager

    from Imervue.gpu_image_view.images import image_loader
    asked = []

    @contextmanager
    def slot(pixels):
        asked.append(pixels)
        yield

    monkeypatch.setattr(image_loader, "decode_slot", slot)
    path = tmp_path / "a.png"
    Image.new("RGB", (30, 20)).save(path)
    mod.LoadThumbnailWorker(str(path), size=size)._bake_fresh(None, "")
    assert asked == [600]
