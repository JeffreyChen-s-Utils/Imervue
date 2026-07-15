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


class TestNameCollisions:
    """The tray is a cross-folder basket, so same-basename entries are normal
    and must not overwrite each other or a pre-existing destination file."""

    def _make(self, folder, name, text):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)
        return str(folder / name)

    def test_copy_all_renames_same_basename_sources(self, tmp_path):
        staging_tray.add(self._make(tmp_path / "a", "photo.jpg", "A"))
        staging_tray.add(self._make(tmp_path / "b", "photo.jpg", "B"))
        dest = tmp_path / "dest"
        dest.mkdir()
        ok, failed = staging_tray.copy_all(str(dest))
        assert (ok, failed) == (2, 0)
        assert sorted(p.read_text() for p in dest.iterdir()) == ["A", "B"]
        assert (dest / "photo.jpg").exists()
        assert (dest / "photo_1.jpg").exists()

    def test_copy_all_does_not_overwrite_existing_dest_file(self, tmp_path):
        staging_tray.add(self._make(tmp_path / "src", "photo.jpg", "NEW"))
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "photo.jpg").write_text("KEEP")
        ok, failed = staging_tray.copy_all(str(dest))
        assert (ok, failed) == (1, 0)
        assert (dest / "photo.jpg").read_text() == "KEEP"     # existing preserved
        assert (dest / "photo_1.jpg").read_text() == "NEW"    # new copy renamed

    def test_move_all_renames_same_basename_sources(self, tmp_path):
        staging_tray.add(self._make(tmp_path / "a", "doc.txt", "A"))
        staging_tray.add(self._make(tmp_path / "b", "doc.txt", "B"))
        dest = tmp_path / "dest"
        dest.mkdir()
        ok, failed = staging_tray.move_all(str(dest))
        assert (ok, failed) == (2, 0)
        assert sorted(p.read_text() for p in dest.iterdir()) == ["A", "B"]
        assert staging_tray.count() == 0
