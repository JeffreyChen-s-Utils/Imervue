"""Tests for moving / copying into a folder without overwriting."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from Imervue.system import file_transfer
from Imervue.system.file_transfer import transfer_into

_CASE_INSENSITIVE = os.path.normcase("A") == os.path.normcase("a")


def _file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("move", [True, False])
def test_an_existing_file_is_never_overwritten(tmp_path, move):
    """shutil.move / copy2 replaced the folder's own IMG_0001.JPG silently."""
    incoming = _file(tmp_path / "card" / "IMG_0001.JPG", "incoming")
    kept = _file(tmp_path / "album" / "IMG_0001.JPG", "already here")
    result = transfer_into([str(incoming)], tmp_path / "album", move=move)
    assert kept.read_text(encoding="utf-8") == "already here"
    renamed = tmp_path / "album" / "IMG_0001_1.JPG"
    assert renamed.read_text(encoding="utf-8") == "incoming"
    assert result.done == [(str(incoming), str(renamed))] and result.failed == []
    assert incoming.exists() is (not move)


def test_two_sources_with_one_name_both_arrive(tmp_path):
    first = _file(tmp_path / "a" / "IMG.JPG", "a")
    second = _file(tmp_path / "b" / "IMG.JPG", "b")
    dest = tmp_path / "dest"
    dest.mkdir()
    transfer_into([str(first), str(second)], dest, move=False)
    assert sorted(p.name for p in dest.iterdir()) == ["IMG.JPG", "IMG_1.JPG"]
    assert {p.read_text(encoding="utf-8") for p in dest.iterdir()} == {"a", "b"}


@pytest.mark.skipif(not _CASE_INSENSITIVE, reason="the file system here tells cases apart")
def test_names_differing_only_in_case_collide_where_the_file_system_ignores_case(tmp_path):
    incoming = _file(tmp_path / "card" / "img_0001.jpg", "incoming")
    kept = _file(tmp_path / "album" / "IMG_0001.JPG", "already here")
    transfer_into([str(incoming)], tmp_path / "album", move=True)
    assert kept.read_text(encoding="utf-8") == "already here"
    assert (tmp_path / "album" / "img_0001_1.jpg").read_text(encoding="utf-8") == "incoming"


def test_moving_into_the_same_folder_is_a_no_op(tmp_path):
    photo = _file(tmp_path / "IMG.JPG", "x")
    result = transfer_into([str(photo)], tmp_path, move=True)
    assert result.done == [(str(photo), str(photo))]
    assert [p.name for p in tmp_path.iterdir()] == ["IMG.JPG"]


def test_copying_into_the_same_folder_makes_a_numbered_copy(tmp_path):
    photo = _file(tmp_path / "IMG.JPG", "x")
    transfer_into([str(photo)], tmp_path, move=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["IMG.JPG", "IMG_1.JPG"]


def test_folders_are_copied_whole(tmp_path):
    _file(tmp_path / "shoot" / "a.jpg", "a")
    dest = tmp_path / "dest"
    _file(dest / "shoot" / "old.jpg", "old")
    transfer_into([str(tmp_path / "shoot")], dest, move=False)
    assert (dest / "shoot" / "old.jpg").exists()
    assert (dest / "shoot_1" / "a.jpg").read_text(encoding="utf-8") == "a"


def test_a_target_appearing_after_planning_is_left_alone(tmp_path, monkeypatch, caplog):
    incoming = _file(tmp_path / "card" / "IMG.JPG", "incoming")
    dest = tmp_path / "dest"
    dest.mkdir()
    real_plan = file_transfer.plan_batch_move

    def plan_then_race(*args, **kwargs):
        plans = real_plan(*args, **kwargs)
        _file(dest / "IMG.JPG", "someone else's")               # written meanwhile
        return plans

    monkeypatch.setattr(file_transfer, "plan_batch_move", plan_then_race)
    with caplog.at_level("WARNING", logger="Imervue"):
        result = transfer_into([str(incoming)], dest, move=True)
    assert result.failed == [str(incoming)] and result.done == []
    assert (dest / "IMG.JPG").read_text(encoding="utf-8") == "someone else's"
    assert incoming.exists()
    assert any("Not overwriting" in r.getMessage() for r in caplog.records)


def test_a_failed_transfer_is_counted_and_the_rest_carry_on(tmp_path, caplog):
    good = _file(tmp_path / "good.jpg", "g")
    dest = tmp_path / "dest"
    dest.mkdir()
    with caplog.at_level("WARNING", logger="Imervue"):
        result = transfer_into([str(tmp_path / "gone.jpg"), str(good)], dest, move=False)
    assert result.failed == [str(tmp_path / "gone.jpg")]
    assert result.done == [(str(good), str(dest / "good.jpg"))]
    assert any("Could not copy" in r.getMessage() for r in caplog.records)
