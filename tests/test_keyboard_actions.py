"""Tests for ``keyboard_actions``: the trash fallback without send2trash, the rating and favourite keys."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QObject

from Imervue.gpu_image_view.actions import keyboard_actions as mod


@pytest.fixture
def linux_fallback(monkeypatch, tmp_path):
    """No send2trash, a Linux platform and a home directory under tmp_path."""
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(sys, "platform", "linux")
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home / ".local" / "share" / "Trash"


def test_moves_the_file_and_writes_trashinfo(linux_fallback, tmp_path):
    victim = tmp_path / "photo.png"
    victim.write_bytes(b"x")
    assert mod._send_to_trash(str(victim)) is True  # noqa: SLF001
    assert not victim.exists()
    assert (linux_fallback / "files" / "photo.png").read_bytes() == b"x"
    info = (linux_fallback / "info" / "photo.png.trashinfo").read_text(encoding="utf-8")
    assert f"Path={victim}" in info


def test_filesystem_failure_returns_false(linux_fallback, tmp_path):
    assert mod._send_to_trash(str(tmp_path / "missing.png")) is False  # noqa: SLF001


def test_unexpected_error_propagates(linux_fallback, tmp_path, monkeypatch):
    import shutil

    def boom(*_a):
        raise RuntimeError("bug")

    victim = tmp_path / "photo.png"
    victim.write_bytes(b"x")
    monkeypatch.setattr(shutil, "move", boom)
    with pytest.raises(RuntimeError):
        mod._send_to_trash(str(victim))  # noqa: SLF001


def test_same_name_trashed_repeatedly_keeps_every_copy(linux_fallback, tmp_path):
    """A timestamp suffix let the third copy within one second overwrite the second."""
    for content in (b"first", b"second", b"third"):
        folder = tmp_path / content.decode()
        folder.mkdir()
        victim = folder / "photo.png"
        victim.write_bytes(content)
        assert mod._send_to_trash(str(victim)) is True  # noqa: SLF001
    files = linux_fallback / "files"
    assert (files / "photo.png").read_bytes() == b"first"
    assert (files / "photo_1.png").read_bytes() == b"second"
    assert (files / "photo_2.png").read_bytes() == b"third"
    assert (linux_fallback / "info" / "photo_1.png.trashinfo").is_file()


def test_free_trash_name_skips_names_with_a_stale_trashinfo(tmp_path):
    files, info = tmp_path / "files", tmp_path / "info"
    files.mkdir()
    info.mkdir()
    (info / "a.png.trashinfo").write_text("", encoding="utf-8")
    (files / "a_1.png").write_bytes(b"")
    assert mod._free_trash_name(files, "a.png", info) == files / "a_2.png"  # noqa: SLF001
    assert mod._free_trash_name(files, "a.png") == files / "a.png"  # noqa: SLF001


def test_macos_fallback_keeps_both(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    for content in (b"first", b"second"):
        folder = tmp_path / content.decode()
        folder.mkdir()
        (folder / "photo.png").write_bytes(content)
        assert mod._send_to_trash(str(folder / "photo.png")) is True  # noqa: SLF001
    trash = tmp_path / "home" / ".Trash"
    assert sorted(p.name for p in trash.iterdir()) == ["photo.png", "photo_1.png"]



def _wall(**kw):
    """A thumbnail wall with three tiles; the last opened picture was the first one."""
    from types import SimpleNamespace
    base = {
        "model": SimpleNamespace(images=["a.jpg", "b.jpg", "c.jpg"]),
        "current_index": 0,
        "tile_grid_mode": True,
        "tile_selection_mode": False,
        "selected_tiles": set(),
        "deep_zoom": None,
        "_hover_last_path": None,
        "focused_tile_index": -1,
        "focus_ring_visible": False,
        "main_window": SimpleNamespace(),
    }
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def ratings():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict["image_ratings"] = {}
    user_setting_dict["image_favorites"] = []
    return user_setting_dict


def test_a_rating_on_the_wall_goes_to_the_hovered_photo(ratings):
    """It went to the last picture opened, which nothing on the wall showed."""
    mod.rate_current_image(_wall(_hover_last_path="c.jpg"), 4)
    assert ratings["image_ratings"] == {"c.jpg": 4}


def test_a_rating_goes_to_the_tile_the_arrow_keys_are_on(ratings):
    mod.rate_current_image(_wall(focused_tile_index=1, focus_ring_visible=True), 2)
    assert ratings["image_ratings"] == {"b.jpg": 2}


def test_a_rating_with_nothing_pointed_at_changes_nothing(ratings):
    mod.rate_current_image(_wall(), 3)
    assert ratings["image_ratings"] == {}


def test_a_rating_reaches_every_selected_tile_and_the_same_key_clears_it(ratings):
    wall = _wall(tile_selection_mode=True, selected_tiles={"a.jpg", "b.jpg"})
    ratings["image_ratings"] = {"a.jpg": 5}
    mod.rate_current_image(wall, 3)
    assert ratings["image_ratings"] == {"a.jpg": 3, "b.jpg": 3}
    mod.rate_current_image(wall, 3)
    assert ratings["image_ratings"] == {}


def test_a_rating_in_deep_zoom_goes_to_the_picture_shown(ratings):
    mod.rate_current_image(_wall(deep_zoom=object(), tile_grid_mode=False, current_index=2), 5)
    assert ratings["image_ratings"] == {"c.jpg": 5}
    mod.rate_current_image(_wall(deep_zoom=object(), tile_grid_mode=False, current_index=2), 5)
    assert ratings["image_ratings"] == {}


def test_the_favourite_key_on_the_wall_takes_the_hovered_photo(ratings):
    mod.toggle_favorite(_wall(_hover_last_path="b.jpg"))
    assert ratings["image_favorites"] == ["b.jpg"]


def test_the_favourite_key_favourites_a_selection_then_unfavourites_it(ratings):
    wall = _wall(tile_selection_mode=True, selected_tiles={"a.jpg", "c.jpg"})
    ratings["image_favorites"] = ["a.jpg"]
    mod.toggle_favorite(wall)
    assert sorted(ratings["image_favorites"]) == ["a.jpg", "c.jpg"]
    mod.toggle_favorite(wall)
    assert ratings["image_favorites"] == []



class _PaintedWall(QObject):
    """A wall that counts its repaints, as the view would."""

    def __init__(self, **kw):
        super().__init__()
        self.__dict__.update(_wall(**kw).__dict__)
        self.updates = 0

    def update(self):
        self.updates += 1


def test_a_rating_repaints_now_and_again_when_its_hud_expires(ratings, qapp, pump_until, monkeypatch):
    """Nothing repainted on a key: the stars and the HUD waited for the next mouse move."""
    monkeypatch.setattr(mod, "_HUD_SECONDS", 0.05)
    wall = _PaintedWall(_hover_last_path="c.jpg")
    mod.rate_current_image(wall, 3)
    assert wall.updates == 1
    assert pump_until(lambda: wall.updates == 2, timeout=3.0)


def test_the_favourite_key_repaints(ratings, qapp):
    wall = _PaintedWall(_hover_last_path="b.jpg")
    mod.toggle_favorite(wall)
    assert wall.updates == 1
