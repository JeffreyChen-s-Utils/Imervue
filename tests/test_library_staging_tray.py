"""
Unit tests for ``Imervue.library.staging_tray``.
"""
from __future__ import annotations

import pytest

from Imervue.library import staging_tray
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_tray():
    user_setting_dict["staging_tray"] = []
    yield
    user_setting_dict["staging_tray"] = []


class TestTrayBasics:
    def test_add_and_count(self):
        assert staging_tray.add("/a/b.png") is True
        assert staging_tray.count() == 1
        assert staging_tray.contains("/a/b.png")

    def test_add_is_idempotent(self):
        staging_tray.add("/x.png")
        assert staging_tray.add("/x.png") is False
        assert staging_tray.count() == 1

    def test_add_many_returns_count(self):
        added = staging_tray.add_many(["/a.png", "/b.png", "/a.png"])
        assert added == 2
        assert staging_tray.count() == 2

    def test_remove(self):
        staging_tray.add("/a.png")
        assert staging_tray.remove("/a.png") is True
        assert staging_tray.remove("/a.png") is False

    def test_clear(self):
        staging_tray.add_many(["/a.png", "/b.png"])
        staging_tray.clear()
        assert staging_tray.count() == 0


class TestBulkOps:
    def test_copy_all(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        staging_tray.add(str(src))
        dest = tmp_path / "dest"
        dest.mkdir()
        ok, failed = staging_tray.copy_all(str(dest))
        assert ok == 1
        assert failed == 0
        assert (dest / "src.txt").read_text() == "hello"
        # Copy leaves tray contents untouched.
        assert staging_tray.count() == 1

    def test_move_all_clears_tray_entries(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        staging_tray.add(str(src))
        dest = tmp_path / "dest"
        dest.mkdir()
        ok, _failed = staging_tray.move_all(str(dest))
        assert ok == 1
        assert staging_tray.count() == 0
        assert not src.exists()

    def test_move_all_bad_dest_raises(self, tmp_path):
        staging_tray.add(str(tmp_path / "x.txt"))
        with pytest.raises(NotADirectoryError):
            staging_tray.move_all(str(tmp_path / "no-such-dir"))
