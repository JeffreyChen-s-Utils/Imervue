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


class TestSidecarsFollowTheirImage:
    """Moving IMG.CR2 left IMG.xmp (a raw developer's edits) behind in the old folder."""

    def test_a_moved_image_takes_every_sidecar_along(self, tmp_path):
        card, album = tmp_path / "card", tmp_path / "album"
        image = _file(card / "IMG.CR2", "raw")
        _file(card / "IMG.xmp", "adobe")
        _file(card / "IMG.CR2.xmp", "darktable")
        _file(card / "IMG.CR2.annotations.json", "notes")
        album.mkdir()
        transfer_into([str(image)], album, move=True)
        assert sorted(p.name for p in card.iterdir()) == []
        assert (album / "IMG.xmp").read_text(encoding="utf-8") == "adobe"
        assert (album / "IMG.CR2.xmp").read_text(encoding="utf-8") == "darktable"
        assert (album / "IMG.CR2.annotations.json").read_text(encoding="utf-8") == "notes"

    def test_a_copied_image_gets_copies_of_its_sidecars(self, tmp_path):
        image = _file(tmp_path / "card" / "IMG.JPG", "jpg")
        _file(tmp_path / "card" / "IMG.xmp", "adobe")
        (tmp_path / "album").mkdir()
        transfer_into([str(image)], tmp_path / "album", move=False)
        assert (tmp_path / "card" / "IMG.xmp").exists()
        assert (tmp_path / "album" / "IMG.xmp").read_text(encoding="utf-8") == "adobe"

    def test_sidecars_take_the_images_new_name(self, tmp_path):
        image = _file(tmp_path / "card" / "IMG.JPG", "incoming")
        _file(tmp_path / "card" / "IMG.xmp", "incoming sidecar")
        _file(tmp_path / "album" / "IMG.JPG", "already here")
        _file(tmp_path / "album" / "IMG.xmp", "its sidecar")
        transfer_into([str(image)], tmp_path / "album", move=True)
        assert (tmp_path / "album" / "IMG.xmp").read_text(encoding="utf-8") == "its sidecar"
        assert (tmp_path / "album" / "IMG_1.xmp").read_text(encoding="utf-8") == "incoming sidecar"

    def test_a_shared_adobe_sidecar_is_copied_while_its_raw_stays(self, tmp_path):
        """IMG.CR2 and IMG.JPG share IMG.xmp; moving the JPEG alone must not strip the RAW."""
        card = tmp_path / "card"
        jpeg = _file(card / "IMG.JPG", "jpg")
        _file(card / "IMG.CR2", "raw")
        _file(card / "IMG.xmp", "edits")
        (tmp_path / "album").mkdir()
        transfer_into([str(jpeg)], tmp_path / "album", move=True)
        assert (card / "IMG.xmp").read_text(encoding="utf-8") == "edits"
        assert (tmp_path / "album" / "IMG.xmp").read_text(encoding="utf-8") == "edits"

    def test_moving_a_raw_jpeg_pair_leaves_no_sidecar_behind(self, tmp_path):
        card = tmp_path / "card"
        pair = [str(_file(card / "IMG.CR2", "raw")), str(_file(card / "IMG.JPG", "jpg"))]
        _file(card / "IMG.xmp", "edits")
        (tmp_path / "album").mkdir()
        result = transfer_into(pair, tmp_path / "album", move=True)
        assert result.failed == []
        assert list(card.iterdir()) == []
        assert sorted(p.name for p in (tmp_path / "album").iterdir()) == [
            "IMG.CR2", "IMG.JPG", "IMG.xmp"]

    def test_a_selected_sidecar_is_not_counted_as_failed(self, tmp_path):
        """The image moved it first; the sidecar's own entry used to fail as missing."""
        card = tmp_path / "card"
        image = _file(card / "IMG.CR2", "raw")
        side = _file(card / "IMG.xmp", "edits")
        (tmp_path / "album").mkdir()
        result = transfer_into([str(image), str(side)], tmp_path / "album", move=True)
        assert result.failed == []
        assert (str(side), str(tmp_path / "album" / "IMG.xmp")) in result.done

    def test_a_different_file_at_the_sidecars_new_name_is_kept(self, tmp_path, caplog):
        image = _file(tmp_path / "card" / "IMG.JPG", "jpg")
        side = _file(tmp_path / "card" / "IMG.JPG.xmp", "mine")
        _file(tmp_path / "album" / "IMG.JPG.xmp", "an orphan")
        with caplog.at_level("WARNING", logger="Imervue"):
            result = transfer_into([str(image)], tmp_path / "album", move=True)
        assert result.failed == []                             # the image itself moved
        assert (tmp_path / "album" / "IMG.JPG.xmp").read_text(encoding="utf-8") == "an orphan"
        assert side.read_text(encoding="utf-8") == "mine"
        assert any("Not overwriting" in r.getMessage() for r in caplog.records)

    def test_a_sidecar_that_cannot_move_does_not_fail_the_image(self, tmp_path, monkeypatch, caplog):
        image = _file(tmp_path / "card" / "IMG.JPG", "jpg")
        _file(tmp_path / "card" / "IMG.xmp", "edits")
        (tmp_path / "album").mkdir()
        real_move = file_transfer.shutil.move

        def refuse_sidecars(src, dst):
            if src.endswith(".xmp"):
                raise PermissionError("locked")
            return real_move(src, dst)

        monkeypatch.setattr(file_transfer.shutil, "move", refuse_sidecars)
        with caplog.at_level("WARNING", logger="Imervue"):
            result = transfer_into([str(image)], tmp_path / "album", move=True)
        assert result.done == [(str(image), str(tmp_path / "album" / "IMG.JPG"))]
        assert (tmp_path / "card" / "IMG.xmp").exists()
        assert any("Could not carry" in r.getMessage() for r in caplog.records)

    def test_folders_bring_no_sidecar_lookup(self, tmp_path):
        _file(tmp_path / "shoot" / "a.jpg", "a")
        _file(tmp_path / "shoot.xmp", "not the folder's")
        (tmp_path / "dest").mkdir()
        transfer_into([str(tmp_path / "shoot")], tmp_path / "dest", move=True)
        assert (tmp_path / "shoot.xmp").exists()


class TestCarryAlongOnRename:
    def test_renamed_file_takes_its_sidecars_and_metadata(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        old = _file(tmp_path / "IMG.JPG", "jpg")
        _file(tmp_path / "IMG.xmp", "edits")
        new = tmp_path / "shot_1.JPG"
        old.rename(new)
        user_setting_dict["image_ratings"] = {str(old): 4}
        file_transfer.carry_along([(str(old), str(new))], move=True)
        assert (tmp_path / "shot_1.xmp").read_text(encoding="utf-8") == "edits"
        assert not (tmp_path / "IMG.xmp").exists()
        assert user_setting_dict["image_ratings"] == {str(new): 4}

    @pytest.mark.skipif(not _CASE_INSENSITIVE, reason="the file system here tells cases apart")
    def test_a_case_only_rename_renames_the_sidecar_too(self, tmp_path):
        old = _file(tmp_path / "img.jpg", "jpg")
        _file(tmp_path / "img.xmp", "edits")
        new = tmp_path / "IMG.jpg"
        old.rename(new)
        file_transfer.carry_along([(str(old), str(new))], move=True)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["IMG.jpg", "IMG.xmp"]

    def test_copies_keep_the_metadata_where_it_was(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        src = _file(tmp_path / "a.jpg", "a")
        user_setting_dict["image_ratings"] = {str(src): 2}
        file_transfer.carry_along([(str(src), str(tmp_path / "b.jpg"))], move=False)
        assert user_setting_dict["image_ratings"] == {str(src): 2}


class TestSavedDataFollowsAMove:
    """Ratings, tags and library notes stayed under the old path after a move."""

    def test_a_moved_file_keeps_its_rating_and_library_note(self, tmp_path):
        from Imervue.library import image_index
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        src = _file(tmp_path / "card" / "IMG.JPG", "jpg")
        (tmp_path / "album").mkdir()
        user_setting_dict["image_ratings"] = {str(src): 5}
        image_index.set_note(str(src), "print this")
        transfer_into([str(src)], tmp_path / "album", move=True)
        moved = str(tmp_path / "album" / "IMG.JPG")
        assert user_setting_dict["image_ratings"] == {moved: 5}
        assert image_index.get_note(moved) == "print this"

    def test_a_copy_leaves_the_saved_data_with_the_original(self, tmp_path):
        from Imervue.library import image_index
        src = _file(tmp_path / "IMG.JPG", "jpg")
        (tmp_path / "album").mkdir()
        image_index.set_note(str(src), "print this")
        transfer_into([str(src)], tmp_path / "album", move=False)
        assert image_index.get_note(str(src)) == "print this"
        assert image_index.get_note(str(tmp_path / "album" / "IMG.JPG")) == ""

    def test_a_moved_folder_brings_the_data_of_every_file_inside(self, tmp_path):
        from Imervue.library import image_index
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        photo = _file(tmp_path / "shoot" / "day1" / "a.jpg", "a")
        (tmp_path / "archive").mkdir()
        user_setting_dict["image_favorites"] = [str(photo)]
        image_index.set_cull_state(str(photo), "pick")
        transfer_into([str(tmp_path / "shoot")], tmp_path / "archive", move=True)
        moved = str(tmp_path / "archive" / "shoot" / "day1" / "a.jpg")
        assert user_setting_dict["image_favorites"] == [moved]
        assert image_index.get_cull_state(moved) == "pick"

    def test_a_library_that_cannot_be_written_is_logged(self, tmp_path, monkeypatch, caplog):
        import sqlite3

        from Imervue.library import image_index

        def locked(*_a, **_k):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(image_index, "move_paths", locked)
        src = _file(tmp_path / "a.jpg", "a")
        (tmp_path / "album").mkdir()
        with caplog.at_level("WARNING", logger="Imervue"):
            result = transfer_into([str(src)], tmp_path / "album", move=True)
        assert result.failed == []
        assert any("re-point the library" in r.getMessage() for r in caplog.records)

    def test_relinking_keeps_what_the_new_path_already_has(self, tmp_path):
        from Imervue.library import image_index
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        old, new = str(tmp_path / "gone.jpg"), str(tmp_path / "found.jpg")
        user_setting_dict["image_ratings"] = {old: 5, new: 2}
        image_index.set_note(old, "old note")
        file_transfer.follow_saved_data({old: new}, keep_existing=True)
        assert user_setting_dict["image_ratings"] == {old: 5, new: 2}
        assert image_index.get_note(new) == "old note"
