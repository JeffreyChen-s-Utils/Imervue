"""Tests for tag and album management helpers."""
from __future__ import annotations

import pytest

from Imervue.user_settings import tags


@pytest.fixture
def usd(monkeypatch):
    """Replace the shared dict + schedule_save with test-local versions."""
    from Imervue.user_settings import user_setting_dict as usd_mod

    store: dict = {}
    saves = {"count": 0}

    def _bump():
        saves["count"] += 1

    monkeypatch.setattr(usd_mod, "user_setting_dict", store, raising=True)
    monkeypatch.setattr(usd_mod, "schedule_save", _bump, raising=True)
    store["_saves"] = saves  # so tests can assert persistence was triggered
    return store


# ---------------------------------------------------------------------------
# Tag operations
# ---------------------------------------------------------------------------


class TestAddTag:
    def test_creates_new_tag_on_first_use(self, usd):
        assert tags.add_tag("sunset", "/p/a.jpg") is True
        assert usd["image_tags"] == {"sunset": ["/p/a.jpg"]}

    def test_appends_to_existing_tag(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        tags.add_tag("sunset", "/p/b.jpg")
        assert usd["image_tags"]["sunset"] == ["/p/a.jpg", "/p/b.jpg"]

    def test_duplicate_path_is_rejected(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        assert tags.add_tag("sunset", "/p/a.jpg") is False
        assert usd["image_tags"]["sunset"] == ["/p/a.jpg"]

    def test_triggers_save(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        assert usd["_saves"]["count"] == 1


class TestRemoveTag:
    def test_removes_existing_pair(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        tags.add_tag("sunset", "/p/b.jpg")
        assert tags.remove_tag("sunset", "/p/a.jpg") is True
        assert usd["image_tags"]["sunset"] == ["/p/b.jpg"]

    def test_unknown_pair_returns_false(self, usd):
        assert tags.remove_tag("missing", "/p/a.jpg") is False

    def test_empty_tag_is_cleaned_up(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        tags.remove_tag("sunset", "/p/a.jpg")
        assert "sunset" not in usd["image_tags"]


class TestCreateTag:
    def test_creates_empty_tag(self, usd):
        assert tags.create_tag("night") is True
        assert usd["image_tags"]["night"] == []

    def test_existing_tag_returns_false(self, usd):
        tags.create_tag("night")
        assert tags.create_tag("night") is False


class TestDeleteTag:
    def test_removes_tag_entry(self, usd):
        tags.create_tag("night")
        assert tags.delete_tag("night") is True
        assert "night" not in usd["image_tags"]

    def test_missing_tag_returns_false(self, usd):
        assert tags.delete_tag("ghost") is False


class TestRenameTag:
    def test_renames_preserving_paths(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        assert tags.rename_tag("sunset", "golden-hour") is True
        assert "sunset" not in usd["image_tags"]
        assert usd["image_tags"]["golden-hour"] == ["/p/a.jpg"]

    def test_missing_source_returns_false(self, usd):
        assert tags.rename_tag("ghost", "anything") is False

    def test_existing_destination_returns_false(self, usd):
        tags.create_tag("a")
        tags.create_tag("b")
        assert tags.rename_tag("a", "b") is False


class TestGetAllTags:
    def test_empty_when_unset(self, usd):
        assert tags.get_all_tags() == {}

    def test_returns_stored_mapping(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        assert tags.get_all_tags() == {"sunset": ["/p/a.jpg"]}


class TestGetTagsForImage:
    def test_none_when_untagged(self, usd):
        assert tags.get_tags_for_image("/p/x.jpg") == []

    def test_returns_all_tags_for_path(self, usd):
        tags.add_tag("sunset", "/p/a.jpg")
        tags.add_tag("wide", "/p/a.jpg")
        tags.add_tag("wide", "/p/b.jpg")
        assert sorted(tags.get_tags_for_image("/p/a.jpg")) == ["sunset", "wide"]
        assert tags.get_tags_for_image("/p/b.jpg") == ["wide"]


# ---------------------------------------------------------------------------
# Album operations
# ---------------------------------------------------------------------------


class TestCreateAlbum:
    def test_creates_empty_album(self, usd):
        assert tags.create_album("vacation") is True
        assert usd["albums"]["vacation"] == []

    def test_duplicate_album_rejected(self, usd):
        tags.create_album("vacation")
        assert tags.create_album("vacation") is False


class TestDeleteAlbum:
    def test_removes_album(self, usd):
        tags.create_album("vacation")
        assert tags.delete_album("vacation") is True
        assert "vacation" not in usd["albums"]

    def test_missing_album_returns_false(self, usd):
        assert tags.delete_album("ghost") is False


class TestRenameAlbum:
    def test_renames_preserving_contents(self, usd):
        tags.add_to_album("vacation", "/p/a.jpg")
        assert tags.rename_album("vacation", "trip") is True
        assert usd["albums"]["trip"] == ["/p/a.jpg"]

    def test_missing_source_returns_false(self, usd):
        assert tags.rename_album("ghost", "other") is False

    def test_existing_destination_returns_false(self, usd):
        tags.create_album("a")
        tags.create_album("b")
        assert tags.rename_album("a", "b") is False


class TestAddToAlbum:
    def test_creates_album_on_first_add(self, usd):
        assert tags.add_to_album("vacation", "/p/a.jpg") is True
        assert usd["albums"]["vacation"] == ["/p/a.jpg"]

    def test_duplicate_path_rejected(self, usd):
        tags.add_to_album("vacation", "/p/a.jpg")
        assert tags.add_to_album("vacation", "/p/a.jpg") is False


class TestRemoveFromAlbum:
    def test_removes_existing_path(self, usd):
        tags.add_to_album("vacation", "/p/a.jpg")
        tags.add_to_album("vacation", "/p/b.jpg")
        assert tags.remove_from_album("vacation", "/p/a.jpg") is True
        assert usd["albums"]["vacation"] == ["/p/b.jpg"]

    def test_missing_path_returns_false(self, usd):
        tags.create_album("vacation")
        assert tags.remove_from_album("vacation", "/p/x.jpg") is False

    def test_missing_album_returns_false(self, usd):
        assert tags.remove_from_album("ghost", "/p/a.jpg") is False

    def test_empty_album_is_kept(self, usd):
        """Unlike tags, empty albums are not auto-deleted."""
        tags.add_to_album("vacation", "/p/a.jpg")
        tags.remove_from_album("vacation", "/p/a.jpg")
        assert "vacation" in usd["albums"]
        assert usd["albums"]["vacation"] == []


class TestGetAlbumImages:
    def test_empty_for_unknown_album(self, usd):
        assert tags.get_album_images("ghost") == []

    def test_returns_copy_not_reference(self, usd):
        tags.add_to_album("vacation", "/p/a.jpg")
        result = tags.get_album_images("vacation")
        result.append("/p/forged.jpg")
        # Mutating the copy must not leak into stored state.
        assert usd["albums"]["vacation"] == ["/p/a.jpg"]


class TestGetAllAlbums:
    def test_empty_when_unset(self, usd):
        assert tags.get_all_albums() == {}

    def test_returns_stored_mapping(self, usd):
        tags.add_to_album("vacation", "/p/a.jpg")
        assert tags.get_all_albums() == {"vacation": ["/p/a.jpg"]}
