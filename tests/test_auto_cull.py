"""Tests for auto-culling blurry images by sharpness."""
from __future__ import annotations

import numpy as np
import pytest

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
