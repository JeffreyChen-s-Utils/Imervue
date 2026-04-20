"""Tests for general-purpose QUndoCommand wrappers (rating, favorite)."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.actions import undo_commands


@pytest.fixture
def usd(monkeypatch):
    from Imervue.user_settings import user_setting_dict as usd_mod

    store: dict = {}
    monkeypatch.setattr(usd_mod, "user_setting_dict", store, raising=True)
    monkeypatch.setattr(usd_mod, "schedule_save", lambda: None, raising=True)
    return store


class TestRatingCommand:
    def test_redo_sets_new_rating(self, usd):
        cmd = undo_commands.RatingCommand("/p/a.jpg", old_rating=None, new_rating=4)
        cmd.redo()
        assert usd["image_ratings"] == {"/p/a.jpg": 4}

    def test_undo_restores_old_rating(self, usd):
        cmd = undo_commands.RatingCommand("/p/a.jpg", old_rating=2, new_rating=5)
        cmd.redo()
        cmd.undo()
        assert usd["image_ratings"] == {"/p/a.jpg": 2}

    def test_redo_none_clears_rating(self, usd):
        usd["image_ratings"] = {"/p/a.jpg": 3}
        cmd = undo_commands.RatingCommand("/p/a.jpg", old_rating=3, new_rating=None)
        cmd.redo()
        assert "/p/a.jpg" not in usd["image_ratings"]

    def test_undo_none_clears_rating(self, usd):
        cmd = undo_commands.RatingCommand("/p/a.jpg", old_rating=None, new_rating=3)
        cmd.redo()
        cmd.undo()
        assert "/p/a.jpg" not in usd.get("image_ratings", {})

    def test_text_includes_filename(self):
        cmd = undo_commands.RatingCommand("/some/dir/photo.jpg", old_rating=0, new_rating=1)
        assert "photo.jpg" in cmd.text()


class TestFavoriteCommand:
    def test_adds_when_not_currently_favorite(self, usd):
        cmd = undo_commands.FavoriteCommand("/p/a.jpg", was_fav=False)
        cmd.redo()
        assert "/p/a.jpg" in usd["image_favorites"]

    def test_removes_when_currently_favorite(self, usd):
        usd["image_favorites"] = ["/p/a.jpg"]
        cmd = undo_commands.FavoriteCommand("/p/a.jpg", was_fav=True)
        cmd.redo()
        assert "/p/a.jpg" not in usd["image_favorites"]

    def test_undo_redo_are_involutions(self, usd):
        cmd = undo_commands.FavoriteCommand("/p/a.jpg", was_fav=False)
        cmd.redo()
        first = list(usd["image_favorites"])
        cmd.undo()
        cmd.redo()
        assert list(usd["image_favorites"]) == first

    def test_text_includes_filename(self):
        cmd = undo_commands.FavoriteCommand("/dir/pic.jpg", was_fav=False)
        assert "pic.jpg" in cmd.text()


class TestRotateCommand:
    """RotateCommand just delegates to rotate_current_image — verify command text."""

    def test_cw_text(self):
        class _FakeGui:
            pass
        cmd = undo_commands.RotateCommand(_FakeGui(), clockwise=True)
        assert "CW" in cmd.text()

    def test_ccw_text(self):
        class _FakeGui:
            pass
        cmd = undo_commands.RotateCommand(_FakeGui(), clockwise=False)
        assert "CCW" in cmd.text()
