"""
Unit tests for ``Imervue.library.token_rename``.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.library.token_rename import apply_plan, preview


_rng = np.random.default_rng(seed=0xC0FFEE)


def _make_image(path: Path, w: int = 16, h: int = 16) -> None:
    arr = _rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    Image.fromarray(arr).save(str(path))


@pytest.fixture
def three_images(tmp_path):
    paths = [tmp_path / f"img{i}.png" for i in range(3)]
    for p in paths:
        _make_image(p)
    return [str(p) for p in paths]


class TestPreview:
    def test_counter_and_name_tokens(self, three_images):
        plans = preview(three_images, "{counter:03}_{name}{ext}")
        names = [Path(plan.dst).name for plan in plans]
        assert names == ["001_img0.png", "002_img1.png", "003_img2.png"]

    def test_wxh_token(self, three_images):
        plans = preview(three_images, "{wxh}{ext}")
        assert Path(plans[0].dst).name == "16x16.png"

    def test_unknown_token_preserved(self, three_images):
        plans = preview(three_images[:1], "{bogus}{ext}")
        assert Path(plans[0].dst).name == "{bogus}.png"

    def test_conflict_flagged_when_destinations_collide(self, three_images):
        plans = preview(three_images, "same{ext}")
        flags = [p.conflict for p in plans]
        assert flags == [False, True, True]

    def test_apply_renames_ok(self, three_images):
        plans = preview(three_images, "renamed_{counter:02}{ext}")
        ok, failed = apply_plan(plans)
        assert ok == 3
        assert failed == 0
        parent = Path(three_images[0]).parent
        remaining = sorted(p.name for p in parent.iterdir())
        assert remaining == ["renamed_01.png", "renamed_02.png", "renamed_03.png"]

    def test_apply_skips_conflicts(self, three_images):
        plans = preview(three_images, "same{ext}")
        ok, failed = apply_plan(plans)
        assert ok == 1
        assert failed == 2
        survivors = os.listdir(Path(three_images[0]).parent)
        assert "same.png" in survivors
