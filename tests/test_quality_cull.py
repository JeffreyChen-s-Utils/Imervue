"""Tests for quality-based auto-cull orchestration."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.library import image_index
from Imervue.library import quality_cull as mod
from Imervue.library.quality_cull import auto_cull_low_quality, score_paths_quality


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def _sharp(_path):
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(32, 32, 3), dtype=np.uint8)


def _flat(_path):
    return np.full((32, 32, 3), 128, dtype=np.uint8)


def test_score_paths_skips_unreadable():
    def boom(_path):
        raise OSError("nope")

    assert score_paths_quality(["a", "b"], boom) == []


def test_cull_flags_worst_fraction():
    # Two sharp + two flat; the flat pair are the worst and get rejected.
    loaders = {"s1": _sharp, "s2": _sharp, "f1": _flat, "f2": _flat}

    def loader(path):
        return loaders[path](path)

    for path in loaders:
        image_index.upsert_image(path, size=1)
    culled = auto_cull_low_quality(list(loaders), fraction=0.5, loader=loader)
    assert culled == 2
    assert image_index.get_cull_state("f1") == image_index.CULL_REJECT
    assert image_index.get_cull_state("s1") != image_index.CULL_REJECT


def test_an_image_over_the_pixel_limit_is_skipped_not_fatal():
    """DecompressionBombError is no OSError: one huge panorama ended the whole batch."""
    from PIL import Image

    def loader(path):
        if path == "huge.png":
            raise Image.DecompressionBombError("too many pixels")
        return _flat(path)

    assert [p for p, _ in score_paths_quality(["huge.png", "blurry.png"], loader)] == ["blurry.png"]


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
