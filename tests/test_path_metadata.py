"""Tests for saved per-image data following a file to its new path."""
from __future__ import annotations

import os

import pytest

from Imervue.user_settings.path_metadata import folder_moves, move_path_metadata, stored_paths
from Imervue.user_settings.user_setting_dict import user_setting_dict

OLD, NEW = r"C:\photos\IMG_0001.JPG", r"D:\album\IMG_0001.JPG"


@pytest.fixture
def saved():
    user_setting_dict.update({
        "image_ratings": {OLD: 5, "other": 1},
        "image_color_labels": {OLD: "red"},
        "image_titles": {OLD: "Harbour"},
        "image_descriptions": {OLD: "At dusk"},
        "image_favorites": ["other", OLD],
        "bookmarks": [OLD],
        "staging_tray": [OLD],
        "reference_pins": ["other", OLD],
        "user_recent_images": [OLD, "other"],
        "image_tags": {"sea": [OLD, "other"], "night": ["other"]},
        "albums": {"Best": [OLD]},
    })
    return user_setting_dict


def test_every_store_follows_the_file(saved):
    assert move_path_metadata({OLD: NEW}) is True
    assert saved["image_ratings"] == {NEW: 5, "other": 1}
    assert saved["image_color_labels"] == {NEW: "red"}
    assert saved["image_titles"] == {NEW: "Harbour"}
    assert saved["image_descriptions"] == {NEW: "At dusk"}
    assert saved["image_favorites"] == ["other", NEW]
    assert saved["bookmarks"] == [NEW]
    assert saved["staging_tray"] == [NEW]
    assert saved["reference_pins"] == ["other", NEW]
    assert saved["user_recent_images"] == [NEW, "other"]
    assert saved["image_tags"] == {"sea": [NEW, "other"], "night": ["other"]}
    assert saved["albums"] == {"Best": [NEW]}


def test_the_bookmark_lookup_sees_the_new_path(saved):
    from Imervue.user_settings.bookmark import is_bookmarked
    assert is_bookmarked(OLD)                      # the lookup cache is warm
    move_path_metadata({OLD: NEW})
    assert is_bookmarked(NEW) and not is_bookmarked(OLD)


def test_data_left_under_the_new_path_by_a_former_file_is_dropped():
    """A deleted IMG_0001.JPG's five stars must not land on the photo moved into its place."""
    user_setting_dict.update({
        "image_ratings": {NEW: 5}, "image_favorites": [NEW], "image_tags": {"x": [NEW]}})
    assert move_path_metadata({OLD: NEW}) is True
    assert user_setting_dict["image_ratings"] == {}
    assert user_setting_dict["image_favorites"] == []
    assert user_setting_dict["image_tags"] == {"x": []}


def test_keep_existing_lets_the_new_paths_data_win():
    user_setting_dict.update({
        "image_ratings": {OLD: 5, NEW: 2}, "image_favorites": [OLD, NEW],
        "image_titles": {OLD: "moved"}})
    move_path_metadata({OLD: NEW}, keep_existing=True)
    assert user_setting_dict["image_ratings"] == {OLD: 5, NEW: 2}
    assert user_setting_dict["image_favorites"] == [OLD, NEW]
    assert user_setting_dict["image_titles"] == {NEW: "moved"}


def test_keep_existing_leaves_a_new_paths_data_alone_when_the_old_has_none():
    user_setting_dict.update({"image_ratings": {NEW: 2}, "image_favorites": [NEW]})
    assert move_path_metadata({OLD: NEW}, keep_existing=True) is False
    assert user_setting_dict["image_ratings"] == {NEW: 2}
    assert user_setting_dict["image_favorites"] == [NEW]


def test_both_paths_listed_collapse_to_one_entry():
    user_setting_dict["image_favorites"] = [OLD, "other", NEW]
    move_path_metadata({OLD: NEW})
    assert user_setting_dict["image_favorites"] == [NEW, "other"]


@pytest.mark.parametrize("mapping", [
    {"b.jpg": "c.jpg", "a.jpg": "b.jpg"}, {"a.jpg": "b.jpg", "b.jpg": "c.jpg"}])
def test_a_chain_of_renames_in_one_batch_moves_each_once(mapping):
    """a→b and b→c together (Batch Rename shifting numbers) must not turn a into c."""
    a, b, c = "a.jpg", "b.jpg", "c.jpg"
    user_setting_dict["image_ratings"] = {a: 1, b: 2}
    user_setting_dict["image_favorites"] = [a, b]
    move_path_metadata(mapping)
    assert user_setting_dict["image_ratings"] == {b: 1, c: 2}
    assert user_setting_dict["image_favorites"] == [b, c]


@pytest.mark.parametrize("mapping", [{}, {OLD: OLD}])
def test_nothing_to_move_changes_nothing(saved, mapping):
    before = {k: saved[k] for k in ("image_ratings", "image_favorites")}
    assert move_path_metadata(mapping) is False
    assert {k: saved[k] for k in before} == before


def test_malformed_stores_are_skipped():
    user_setting_dict.update({"image_ratings": ["not", "a", "dict"], "image_favorites": {OLD},
                              "image_tags": {"x": "not a list"}, "albums": None})
    assert move_path_metadata({OLD: NEW}) is False


def test_a_change_is_saved(saved, monkeypatch):
    from Imervue.user_settings import user_setting_dict as module
    calls = []
    monkeypatch.setattr(module, "schedule_save", lambda: calls.append(1))
    move_path_metadata({OLD: NEW})
    assert calls == [1]


class TestFolderMoves:
    def test_maps_every_path_inside_the_folder(self, tmp_path):
        old, new = tmp_path / "shoot", tmp_path / "2024" / "shoot"
        inside = [str(old / "a.jpg"), str(old / "sub" / "b.jpg")]
        outside = [str(tmp_path / "shoot2" / "c.jpg"), str(tmp_path / "shoot.jpg")]
        assert folder_moves(str(old), str(new), inside + outside) == {
            inside[0]: str(new / "a.jpg"), inside[1]: str(new / "sub" / "b.jpg")}

    @pytest.mark.skipif(os.path.normcase("A") != os.path.normcase("a"),
                        reason="the file system here tells cases apart")
    def test_matches_the_folder_as_the_file_system_does(self, tmp_path):
        stored = (tmp_path / "Shoot" / "A.jpg").as_posix().lower()     # other case, "/"
        moves = folder_moves(str(tmp_path / "SHOOT"), str(tmp_path / "x"), [stored])
        assert moves == {stored: str(tmp_path / "x" / "a.jpg")}

    def test_nothing_inside_gives_nothing(self, tmp_path):
        assert folder_moves(str(tmp_path / "a"), str(tmp_path / "b"), []) == {}


def test_stored_paths_lists_every_store(saved):
    assert stored_paths() == {OLD, "other"}
