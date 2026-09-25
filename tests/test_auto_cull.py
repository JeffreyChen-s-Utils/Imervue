"""Tests for auto-culling blurry images by sharpness."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.library import auto_cull as mod
from Imervue.library import image_index
from Imervue.library.auto_cull import auto_cull_blurry, score_paths


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


_SHARP = ((np.indices((16, 16)).sum(axis=0) % 2) * 255).astype(np.float64)
_BLURRY = np.full((16, 16), 128.0)


def _fake_loader(path: str) -> np.ndarray:
    return {"sharp.png": _SHARP, "blurry.png": _BLURRY}[path]


def test_score_paths_uses_loader():
    scores = dict(score_paths(["sharp.png", "blurry.png"], _fake_loader))
    assert scores["sharp.png"] > scores["blurry.png"]


def test_score_paths_skips_unreadable():
    def loader(_p):
        raise OSError("nope")
    assert score_paths(["x.png"], loader) == []


def test_auto_cull_flags_blurry_as_reject():
    count = auto_cull_blurry(
        ["sharp.png", "blurry.png"], threshold=100.0, loader=_fake_loader,
    )
    assert count == 1
    assert image_index.filter_by_cull(
        ["sharp.png", "blurry.png"], image_index.CULL_REJECT) == ["blurry.png"]


def test_auto_cull_none_below_threshold():
    count = auto_cull_blurry(["sharp.png"], threshold=0.0, loader=_fake_loader)
    assert count == 0


def test_an_image_over_the_pixel_limit_is_skipped_not_fatal():
    """DecompressionBombError is no OSError: one huge panorama ended the whole batch."""
    from PIL import Image

    def loader(path):
        if path == "huge.png":
            raise Image.DecompressionBombError("too many pixels")
        return _fake_loader(path)

    assert [p for p, _ in score_paths(["huge.png", "blurry.png"], loader)] == ["blurry.png"]


def test_the_default_loader_reads_a_camera_raw_through_the_viewer(tmp_path, monkeypatch):
    """Image.open read a RAW's tiny TIFF thumbnail (or nothing, for CR3)."""
    from PIL import Image

    from Imervue.gpu_image_view.images import image_loader
    calls = []

    def develop(_path, thumbnail):
        calls.append(thumbnail)
        return np.zeros((1000, 1500, 3), dtype=np.uint8)

    monkeypatch.setattr(image_loader, "_load_raw", develop)
    raw = tmp_path / "shot.cr2"
    Image.new("RGB", (5, 3)).save(raw, format="TIFF")      # all Pillow sees
    arr = mod._load_for_scoring(str(raw))
    assert calls == [True]                                  # the fast preview decode
    assert arr.shape[:2] == (341, 512)


def test_the_default_loader_turns_a_photo_upright(tmp_path):
    from PIL import Image
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20), "white").save(path, exif=exif)
    assert mod._load_for_scoring(str(path)).shape[:2] == (40, 20)
