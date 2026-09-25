"""Tests for batch_rename: renames whose targets are other files' current names."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from Imervue.system import batch_rename
from Imervue.system.batch_rename import rename_files


def _files(folder: Path, *names: str) -> list[str]:
    for name in names:
        (folder / name).write_text(name, encoding="utf-8")
    return [str(folder / name) for name in names]


def _contents(folder: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in folder.iterdir()}


class TestOrdering:
    def test_renumbering_up_by_one_lands_whole(self, tmp_path):
        """001→002 used to be refused because 002 was still there."""
        paths = _files(tmp_path, "001.jpg", "002.jpg", "003.jpg")
        renamed, failed = rename_files(
            [(p, str(tmp_path / f"{n:03}.jpg")) for n, p in enumerate(paths, start=2)])
        assert failed == 0
        assert len(renamed) == 3
        assert _contents(tmp_path) == {"002.jpg": "001.jpg", "003.jpg": "002.jpg",
                                       "004.jpg": "003.jpg"}

    def test_renumbering_down_closes_a_gap(self, tmp_path):
        paths = _files(tmp_path, "003.jpg", "004.jpg")
        renamed, failed = rename_files(
            [(paths[0], str(tmp_path / "002.jpg")), (paths[1], str(tmp_path / "003.jpg"))])
        assert (len(renamed), failed) == (2, 0)
        assert _contents(tmp_path) == {"002.jpg": "003.jpg", "003.jpg": "004.jpg"}

    def test_two_names_swap(self, tmp_path):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        renamed, failed = rename_files([(a, b), (b, a)])
        assert sorted(renamed) == [(a, b), (b, a)]
        assert failed == 0
        assert _contents(tmp_path) == {"a.jpg": "b.jpg", "b.jpg": "a.jpg"}

    def test_a_three_way_cycle_rotates(self, tmp_path):
        a, b, c = _files(tmp_path, "a.jpg", "b.jpg", "c.jpg")
        renamed, failed = rename_files([(a, b), (b, c), (c, a)])
        assert (len(renamed), failed) == (3, 0)
        assert _contents(tmp_path) == {"a.jpg": "c.jpg", "b.jpg": "a.jpg", "c.jpg": "b.jpg"}

    def test_a_long_chain_listed_front_to_back(self, tmp_path):
        names = [f"{n:03}.jpg" for n in range(1, 41)]
        paths = _files(tmp_path, *names)
        renamed, failed = rename_files(
            [(p, str(tmp_path / f"{n:03}.jpg")) for n, p in enumerate(paths, start=2)])
        assert (len(renamed), failed) == (40, 0)
        assert (tmp_path / "041.jpg").read_text(encoding="utf-8") == "040.jpg"
        assert not (tmp_path / "001.jpg").exists()

    def test_a_case_only_rename(self, tmp_path):
        (a,) = _files(tmp_path, "img.jpg")
        renamed, failed = rename_files([(a, str(tmp_path / "IMG.jpg"))])
        assert (len(renamed), failed) == (1, 0)
        assert os.listdir(tmp_path) == ["IMG.jpg"]


class TestRefusals:
    def test_empty_batch(self):
        assert rename_files([]) == ([], 0)

    def test_an_unchanged_name_is_not_renamed(self, tmp_path):
        (a,) = _files(tmp_path, "a.jpg")
        assert rename_files([(a, a)]) == ([], 1)
        assert _contents(tmp_path) == {"a.jpg": "a.jpg"}

    def test_a_file_outside_the_batch_is_never_overwritten(self, tmp_path):
        a, _b = _files(tmp_path, "a.jpg", "b.jpg")
        assert rename_files([(a, str(tmp_path / "b.jpg"))]) == ([], 1)
        assert _contents(tmp_path) == {"a.jpg": "a.jpg", "b.jpg": "b.jpg"}

    def test_the_first_claim_on_a_name_wins(self, tmp_path):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        target = str(tmp_path / "c.jpg")
        assert rename_files([(a, target), (b, target)]) == ([(a, target)], 1)
        assert _contents(tmp_path) == {"b.jpg": "b.jpg", "c.jpg": "a.jpg"}

    def test_a_source_listed_twice_moves_once(self, tmp_path):
        (a,) = _files(tmp_path, "a.jpg")
        renamed, failed = rename_files([(a, str(tmp_path / "b.jpg")), (a, str(tmp_path / "c.jpg"))])
        assert (renamed, failed) == ([(a, str(tmp_path / "b.jpg"))], 1)

    def test_a_name_whose_holder_stays_is_refused(self, tmp_path):
        """b.jpg is in the batch but keeps its name, so a.jpg can't take it."""
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        assert rename_files([(b, b), (a, b)]) == ([], 2)
        assert _contents(tmp_path) == {"a.jpg": "a.jpg", "b.jpg": "b.jpg"}

    def test_a_missing_source_fails_alone(self, tmp_path):
        (a,) = _files(tmp_path, "a.jpg")
        ghost = str(tmp_path / "ghost.jpg")
        renamed, failed = rename_files([(ghost, str(tmp_path / "x.jpg")),
                                        (a, str(tmp_path / "y.jpg"))])
        assert (renamed, failed) == ([(a, str(tmp_path / "y.jpg"))], 1)


class TestFailures:
    def test_a_refused_rename_stops_the_one_waiting_for_its_name(self, tmp_path, monkeypatch):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        c = str(tmp_path / "c.jpg")
        real_rename = os.rename

        def refuse_b(src, dst):
            if Path(src).name == "b.jpg":
                raise PermissionError("in use")
            real_rename(src, dst)

        monkeypatch.setattr(batch_rename.os, "rename", refuse_b)
        renamed, failed = rename_files([(a, b), (b, c)])
        assert (renamed, failed) == ([], 2)
        assert _contents(tmp_path) == {"a.jpg": "a.jpg", "b.jpg": "b.jpg"}

    def test_a_parked_file_whose_rename_fails_gets_its_name_back(self, tmp_path, monkeypatch):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        real_rename = os.rename

        def refuse_b(src, dst):
            if Path(src).name == "b.jpg":
                raise PermissionError("in use")
            real_rename(src, dst)

        monkeypatch.setattr(batch_rename.os, "rename", refuse_b)
        renamed, failed = rename_files([(a, b), (b, a)])
        assert (renamed, failed) == ([], 2)
        assert _contents(tmp_path) == {"a.jpg": "a.jpg", "b.jpg": "b.jpg"}

    def test_a_cycle_that_cannot_park_renames_nothing(self, tmp_path, monkeypatch):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        real_rename = os.rename

        def refuse_parking(src, dst):
            if "-renaming-" in Path(dst).name:
                raise PermissionError("read-only folder")
            real_rename(src, dst)

        monkeypatch.setattr(batch_rename.os, "rename", refuse_parking)
        assert rename_files([(a, b), (b, a)]) == ([], 2)
        assert _contents(tmp_path) == {"a.jpg": "a.jpg", "b.jpg": "b.jpg"}

    def test_a_parked_file_whose_old_name_was_taken_is_logged(self, tmp_path, monkeypatch, caplog):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        real_rename = os.rename

        def squat_then_refuse(src, dst):
            if Path(src).name == "b.jpg":
                (tmp_path / "a.jpg").write_text("squatter", encoding="utf-8")
                raise PermissionError("in use")
            real_rename(src, dst)

        monkeypatch.setattr(batch_rename.os, "rename", squat_then_refuse)
        with caplog.at_level("ERROR", logger="Imervue.batch_rename"):
            assert rename_files([(a, b), (b, a)]) == ([], 2)
        parked = [name for name in os.listdir(tmp_path) if "-renaming-" in name]
        assert len(parked) == 1
        assert (tmp_path / parked[0]).read_text(encoding="utf-8") == "a.jpg"
        assert "was left as" in caplog.text


class TestWhatFollows:
    def test_sidecars_swap_with_their_images(self, tmp_path):
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        (tmp_path / "a.jpg.xmp").write_text("a-edits", encoding="utf-8")
        (tmp_path / "b.xmp").write_text("b-edits", encoding="utf-8")
        rename_files([(a, b), (b, a)])
        assert _contents(tmp_path) == {"a.jpg": "b.jpg", "b.jpg": "a.jpg",
                                       "b.jpg.xmp": "a-edits", "a.xmp": "b-edits"}

    def test_saved_ratings_follow_a_renumbering(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        first, second = _files(tmp_path, "001.jpg", "002.jpg")
        third = str(tmp_path / "003.jpg")
        user_setting_dict["image_ratings"] = {first: 1, second: 2}
        rename_files([(first, second), (second, third)])
        assert user_setting_dict["image_ratings"] == {second: 1, third: 2}

    def test_saved_ratings_swap(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        a, b = _files(tmp_path, "a.jpg", "b.jpg")
        user_setting_dict["image_ratings"] = {a: 5, b: 1}
        rename_files([(a, b), (b, a)])
        assert user_setting_dict["image_ratings"] == {b: 5, a: 1}

    def test_nothing_saved_moves_when_nothing_was_renamed(self, tmp_path, monkeypatch):
        called = []
        monkeypatch.setattr(batch_rename, "follow_saved_data", called.append)
        (a,) = _files(tmp_path, "a.jpg")
        rename_files([(a, a)])
        assert called == []


@pytest.mark.parametrize("name", ["IMG.JPG", "README", ".hidden"])
def test_parking_name_keeps_the_extension(tmp_path, name):
    parked = Path(batch_rename._parking_name(str(tmp_path / name)))  # noqa: SLF001
    assert parked.parent == tmp_path
    assert parked.suffix == Path(name).suffix
    assert "-renaming-" in parked.name
