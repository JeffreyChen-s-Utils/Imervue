"""Tests for user settings and recent images."""
import json
from pathlib import Path

import pytest


class TestUserSettingDict:
    def test_write_and_read(self, tmp_path, monkeypatch):
        """Settings should round-trip through JSON."""
        monkeypatch.chdir(tmp_path)

        from Imervue.user_settings.user_setting_dict import (
            user_setting_dict, write_user_setting, read_user_setting,
        )

        # Set some values
        user_setting_dict["language"] = "Japanese"
        user_setting_dict["user_last_folder"] = "/test/folder"

        # Write
        path = write_user_setting()
        assert path.exists()

        # Verify JSON content
        data = json.loads(path.read_text())
        assert data["language"] == "Japanese"
        assert data["user_last_folder"] == "/test/folder"

        # Reset and read back
        user_setting_dict["language"] = "English"
        user_setting_dict["user_last_folder"] = ""
        read_user_setting()
        assert user_setting_dict["language"] == "Japanese"
        assert user_setting_dict["user_last_folder"] == "/test/folder"

        # Cleanup: restore defaults
        user_setting_dict["language"] = "English"
        user_setting_dict["user_last_folder"] = ""

    def test_read_missing_file(self, tmp_path, monkeypatch):
        """Reading when no settings file exists should not crash."""
        monkeypatch.chdir(tmp_path)
        from Imervue.user_settings.user_setting_dict import read_user_setting
        path = read_user_setting()
        # Should return path even if file doesn't exist
        assert isinstance(path, Path)


class TestRecentImage:
    def test_add_recent_folder(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.recent_image import add_recent_folder

        user_setting_dict["user_recent_folders"] = []
        add_recent_folder("/folder/a")
        add_recent_folder("/folder/b")
        assert user_setting_dict["user_recent_folders"] == ["/folder/b", "/folder/a"]

    def test_add_duplicate_moves_to_front(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.recent_image import add_recent_folder

        user_setting_dict["user_recent_folders"] = []
        add_recent_folder("/folder/a")
        add_recent_folder("/folder/b")
        add_recent_folder("/folder/a")
        assert user_setting_dict["user_recent_folders"] == ["/folder/a", "/folder/b"]

    def test_max_recent_limit(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.recent_image import add_recent_folder, MAX_RECENT

        user_setting_dict["user_recent_folders"] = []
        for i in range(MAX_RECENT + 5):
            add_recent_folder(f"/folder/{i}")
        assert len(user_setting_dict["user_recent_folders"]) == MAX_RECENT

    def test_add_recent_image(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.recent_image import add_recent_image

        user_setting_dict["user_recent_images"] = []
        add_recent_image("/img/a.png")
        add_recent_image("/img/b.jpg")
        assert user_setting_dict["user_recent_images"] == ["/img/b.jpg", "/img/a.png"]

    def test_clear_recent(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.recent_image import add_recent_folder, add_recent_image, clear_recent

        add_recent_folder("/f")
        add_recent_image("/i.png")
        clear_recent()
        assert user_setting_dict["user_recent_folders"] == []
        assert user_setting_dict["user_recent_images"] == []
