"""Tests for user settings and recent images.

Isolation is handled by the ``_isolate_user_settings`` autouse fixture
in ``conftest.py`` — it redirects the settings file to a per-test tmp
path and cancels pending debounced saves on teardown so timers can't
clobber the real file from a later test.
"""
import json
from pathlib import Path



class TestUserSettingDict:
    def test_write_and_read(self):
        """Settings should round-trip through JSON in the v2 multi-profile format."""
        from Imervue.user_settings.user_setting_dict import (
            DEFAULT_PROFILE,
            read_user_setting,
            user_setting_dict,
            write_user_setting,
        )

        # Set some values
        user_setting_dict["language"] = "Japanese"
        user_setting_dict["user_last_folder"] = "/test/folder"

        # Write
        path = write_user_setting()
        assert path.exists()

        # Verify v2 container shape: {"current_profile": ..., "profiles": {...}}
        data = json.loads(path.read_text())
        assert data["current_profile"] == DEFAULT_PROFILE
        assert "profiles" in data
        default_profile = data["profiles"][DEFAULT_PROFILE]
        assert default_profile["language"] == "Japanese"
        assert default_profile["user_last_folder"] == "/test/folder"

        # Reset and read back
        user_setting_dict["language"] = "English"
        user_setting_dict["user_last_folder"] = ""
        read_user_setting()
        assert user_setting_dict["language"] == "Japanese"
        assert user_setting_dict["user_last_folder"] == "/test/folder"

    def test_read_missing_file(self):
        """Reading when no settings file exists should not crash."""
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


class TestReadJson:
    def test_reads_a_valid_file(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import read_json
        path = tmp_path / "s.json"
        path.write_text('{"a": [1, 2]}', encoding="utf-8")
        assert read_json(str(path)) == {"a": [1, 2]}

    def test_missing_file_and_directory_give_none(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import read_json
        assert read_json(str(tmp_path / "absent.json")) is None
        assert read_json(str(tmp_path)) is None

    def test_unreadable_contents_give_none(self, tmp_path):
        from Imervue.user_settings.user_setting_dict import read_json
        cases = {"bad.json": b"{not json", "latin.json": b'{"a": "\xff"}',
                 "deep.json": b"[" * 200_000 + b"]" * 200_000}
        for name, data in cases.items():
            (tmp_path / name).write_bytes(data)
            assert read_json(str(tmp_path / name)) is None, name

    def test_unexpected_errors_propagate_and_release_the_lock(self, tmp_path, monkeypatch):
        import pytest

        from Imervue.user_settings import user_setting_dict as mod
        path = tmp_path / "s.json"
        path.write_text("{}", encoding="utf-8")

        def boom(_text):
            raise RuntimeError("bug")

        monkeypatch.setattr(mod.json, "loads", boom)
        with pytest.raises(RuntimeError):
            mod.read_json(str(path))
        assert mod._lock.acquire(blocking=False)  # noqa: SLF001
        mod._lock.release()  # noqa: SLF001


class TestUnreadableSettingsFile:
    """A settings file that could not be read at start-up was replaced by the first save."""

    BROKEN = '{"current_profile": "default", "profiles": {"default": {"image_ratings": {"a.jpg": 5}'

    @staticmethod
    def _path(tmp_path):
        return tmp_path / "user_setting.json"

    @staticmethod
    def _copies(tmp_path):
        return sorted(tmp_path.glob("user_setting.json.unreadable-*"))

    def test_a_copy_is_kept_before_the_first_save(self, tmp_path):
        from Imervue.user_settings import user_setting_dict as mod
        path = self._path(tmp_path)
        path.write_text(self.BROKEN, encoding="utf-8")
        mod.read_user_setting()
        mod.user_setting_dict["language"] = "Japanese"
        mod.write_user_setting()
        (copy,) = self._copies(tmp_path)
        assert copy.read_text(encoding="utf-8") == self.BROKEN
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["profiles"]["default"]["language"] == "Japanese"

    def test_only_the_first_save_keeps_a_copy(self, tmp_path):
        from Imervue.user_settings import user_setting_dict as mod
        self._path(tmp_path).write_text(self.BROKEN, encoding="utf-8")
        mod.read_user_setting()
        mod.write_user_setting()
        mod.write_user_setting()
        assert len(self._copies(tmp_path)) == 1

    def test_a_readable_file_keeps_no_copy(self, tmp_path):
        from Imervue.user_settings import user_setting_dict as mod
        mod.write_user_setting()
        mod.read_user_setting()
        mod.write_user_setting()
        assert self._copies(tmp_path) == []

    def test_no_file_at_start_keeps_no_copy(self, tmp_path):
        from Imervue.user_settings import user_setting_dict as mod
        mod.read_user_setting()
        mod.write_user_setting()
        assert self._path(tmp_path).exists()
        assert self._copies(tmp_path) == []

    def test_a_file_held_at_start_is_kept_before_it_is_saved_over(self, tmp_path, monkeypatch):
        """Unreadable only for a moment (another program held it): its ratings survive in the copy."""
        from Imervue.user_settings import user_setting_dict as mod
        path = self._path(tmp_path)
        good = {"current_profile": "default",
                "profiles": {"default": {"image_ratings": {"a.jpg": 5}}}}
        path.write_text(json.dumps(good), encoding="utf-8")
        real_read_json = mod.read_json
        monkeypatch.setattr(mod, "read_json", lambda _p: None)
        mod.read_user_setting()
        monkeypatch.setattr(mod, "read_json", real_read_json)
        mod.write_user_setting()
        (copy,) = self._copies(tmp_path)
        assert json.loads(copy.read_text(encoding="utf-8")) == good

    def test_nothing_is_saved_over_it_when_no_copy_can_be_kept(self, tmp_path, monkeypatch):
        import shutil

        from Imervue.user_settings import user_setting_dict as mod
        path = self._path(tmp_path)
        path.write_text(self.BROKEN, encoding="utf-8")
        mod.read_user_setting()
        real_copy2 = shutil.copy2
        disk_full = True

        def copy2(src, dst, **kwargs):
            if disk_full:
                raise PermissionError("disk full")
            return real_copy2(src, dst, **kwargs)

        monkeypatch.setattr(shutil, "copy2", copy2)
        mod.write_user_setting()
        assert mod._save_settings(path, {"profiles": {}}) is False   # the profile actions' writer
        assert path.read_text(encoding="utf-8") == self.BROKEN
        assert self._copies(tmp_path) == []
        disk_full = False
        mod.write_user_setting()                  # a later save, once the copy can be made
        (copy,) = self._copies(tmp_path)
        assert copy.read_text(encoding="utf-8") == self.BROKEN
        assert json.loads(path.read_text(encoding="utf-8"))["current_profile"] == "default"
