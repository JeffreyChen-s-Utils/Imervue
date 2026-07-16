"""
Unit tests for ``Imervue.library.token_rename``.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.library.token_rename import (
    _EPOCH,
    _apply_string_format,
    _safe_fromtimestamp,
    apply_plan,
    preview,
)


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


class TestCrossFolderConflicts:
    """Collision detection must key on the full destination path, not the bare
    basename: two files in different folders can render to the same name without
    actually colliding, and keying on the basename dropped every folder after the
    first as a false conflict."""

    def test_same_name_different_folders_is_not_a_conflict(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        _make_image(a / "x.png")
        _make_image(b / "y.png")
        plans = preview([str(a / "x.png"), str(b / "y.png")], "photo{ext}")
        assert [Path(p.dst).name for p in plans] == ["photo.png", "photo.png"]
        assert [p.conflict for p in plans] == [False, False]

    def test_same_name_same_folder_is_a_conflict(self, tmp_path):
        _make_image(tmp_path / "a.png")
        _make_image(tmp_path / "b.png")
        plans = preview(
            [str(tmp_path / "a.png"), str(tmp_path / "b.png")], "same{ext}")
        assert plans[0].conflict is False
        assert plans[1].conflict is True   # real in-folder collision


class TestSafeFromTimestamp:
    """Out-of-range mtimes must not abort the whole rename preview."""

    def test_far_future_clamps_to_epoch(self):
        assert _safe_fromtimestamp(10 ** 18) == _EPOCH

    def test_far_past_clamps_to_epoch(self):
        assert _safe_fromtimestamp(-(10 ** 18)) == _EPOCH

    def test_normal_timestamp_passes_through(self):
        # A representable timestamp is returned, not the epoch fallback.
        result = _safe_fromtimestamp(1_600_000_000)   # 2020-09-13 UTC
        assert result.year == 2020

    def test_date_token_preview_survives_bad_mtime(self, tmp_path, monkeypatch):
        # With the raw conversion forced to raise, the guard must keep preview()
        # alive (falling back to the epoch) instead of aborting the batch.
        import Imervue.library.token_rename as tr

        def boom(_ts):
            raise OverflowError("out of range")

        monkeypatch.setattr(
            tr, "datetime", type("D", (), {"fromtimestamp": staticmethod(boom)}))
        p = tmp_path / "img.png"
        _make_image(p)
        plans = preview([str(p)], "{date}{ext}")   # must not raise
        assert len(plans) == 1


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

    def test_parent_token(self, three_images):
        parent_name = Path(three_images[0]).parent.name
        plans = preview(three_images[:1], "{parent}_{name}{ext}")
        assert Path(plans[0].dst).name == f"{parent_name}_img0.png"

    def test_case_transform_on_name(self, three_images):
        plans = preview(three_images[:1], "{name:upper}{ext}")
        assert Path(plans[0].dst).name == "IMG0.png"

    def test_unknown_transform_leaves_value_unchanged(self, three_images):
        plans = preview(three_images[:1], "{name:bogus}{ext}")
        assert Path(plans[0].dst).name == "img0.png"


class TestApplyStringFormat:
    def test_upper(self):
        assert _apply_string_format("Photo", "upper") == "PHOTO"

    def test_lower(self):
        assert _apply_string_format("Photo", "lower") == "photo"

    def test_title(self):
        assert _apply_string_format("my photo", "title") == "My Photo"

    def test_none_format_is_identity(self):
        assert _apply_string_format("Photo", None) == "Photo"

    def test_unknown_format_is_identity(self):
        assert _apply_string_format("Photo", "rot13") == "Photo"

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
