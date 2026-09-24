"""Tests for ``LoadThumbnailWorker._load_raw``: embedded preview first, full decode as fallback."""
from __future__ import annotations

import io

import numpy as np
import pytest
import rawpy
from PIL import Image

from Imervue.gpu_image_view.images import load_thumbnail_worker as mod

_DECODED = np.full((6, 8, 3), 200, dtype=np.uint8)


class _FakeRaw:
    def __init__(self, thumb):
        self._thumb = thumb
        self.postprocessed = False

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def extract_thumb(self):
        if isinstance(self._thumb, Exception):
            raise self._thumb
        return self._thumb

    def postprocess(self, **_kw):
        self.postprocessed = True
        return _DECODED


def _load(monkeypatch, thumb):
    raw = _FakeRaw(thumb)
    real_imread = rawpy.imread
    # imageio's own rawpy plugin calls rawpy.imread too; only intercept ours.
    monkeypatch.setattr(rawpy, "imread",
                        lambda path, *a, **k: raw if path == "shot.cr2" else real_imread(path, *a, **k))
    worker = mod.LoadThumbnailWorker("shot.cr2", size=None)
    return worker._load_raw(), raw  # noqa: SLF001


def _jpeg_thumb():
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), "red").save(buf, "JPEG")
    return type("Thumb", (), {"format": rawpy.ThumbFormat.JPEG, "data": buf.getvalue()})()


def test_uses_the_embedded_jpeg(monkeypatch):
    data, raw = _load(monkeypatch, _jpeg_thumb())
    assert data.shape == (6, 8, 3) and not raw.postprocessed


# Decoding junk makes imageio try its vendored tifffile plugin, which warns.
@pytest.mark.filterwarnings("ignore::DeprecationWarning:imageio")
@pytest.mark.parametrize("failure", [
    rawpy.LibRawNoThumbnailError(), rawpy.LibRawUnsupportedThumbnailError(),
    type("Thumb", (), {"format": "other", "data": b""})(),                   # no valid preview
    type("Thumb", (), {"format": rawpy.ThumbFormat.JPEG, "data": b"junk"})(),  # undecodable
])
def test_falls_back_to_a_full_decode(monkeypatch, failure):
    data, raw = _load(monkeypatch, failure)
    assert raw.postprocessed
    assert np.array_equal(data, _DECODED)


def test_unexpected_error_propagates(monkeypatch):
    with pytest.raises(RuntimeError):
        _load(monkeypatch, RuntimeError("bug"))


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

