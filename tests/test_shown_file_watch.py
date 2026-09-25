"""Tests for reloading the deep-zoom picture when another program rewrites its file."""
from __future__ import annotations

import os

import pytest

from Imervue.gpu_image_view import shown_file_watch
from Imervue.gpu_image_view.shown_file_watch import ShownFileWatch


@pytest.fixture
def watch(qapp, monkeypatch):
    """A watch whose picture is always on screen, recording each reload."""
    monkeypatch.setattr(shown_file_watch, "SETTLE_MS", 20)
    reloads: list[str] = []
    shown: dict[str, bool] = {"yes": True}
    w = ShownFileWatch(lambda _path: shown["yes"], reloads.append)
    w.reloads, w.shown = reloads, shown
    yield w
    w.follow(None)
    w.deleteLater()


def _picture(tmp_path, name="a.png", size=100):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return str(path)


def test_follow_watches_the_file_and_none_stops(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    assert watch.path == path
    assert watch._watcher.files() == [path]
    watch.follow(None)
    assert watch.path is None
    assert watch._watcher.files() == []


def test_following_another_picture_drops_the_first(watch, tmp_path):
    first, second = _picture(tmp_path, "a.png"), _picture(tmp_path, "b.png")
    watch.follow(first)
    watch.follow(second)
    assert watch._watcher.files() == [second]
    watch._on_file_changed(first)
    assert not watch._settle.isActive()


def test_a_missing_file_is_not_watched(watch, tmp_path):
    missing = str(tmp_path / "gone.png")
    watch.follow(missing)
    assert watch._watcher.files() == []
    watch._check()
    assert watch.reloads == []


def test_an_in_place_rewrite_reloads(watch, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    with open(path, "r+b") as handle:
        handle.write(b"y" * 300)
    assert pump_until(lambda: watch.reloads == [path])


def test_a_copy_renamed_over_the_file_reloads(watch, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    copy = tmp_path / "a.png.tmp"
    copy.write_bytes(b"z" * 300)
    os.replace(copy, path)
    assert pump_until(lambda: watch.reloads == [path])


def test_a_second_rewrite_reloads_again(watch, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    with open(path, "r+b") as handle:
        handle.write(b"y" * 300)
    assert pump_until(lambda: len(watch.reloads) == 1)
    with open(path, "ab") as handle:
        handle.write(b"more")
    assert pump_until(lambda: len(watch.reloads) == 2)


def test_an_unchanged_file_is_not_reloaded(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    watch._check()
    assert watch.reloads == []


def test_a_picture_no_longer_shown_is_not_reloaded(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    (tmp_path / "a.png").write_bytes(b"y" * 300)
    watch.shown["yes"] = False
    watch._check()
    assert watch.reloads == []


def test_a_removed_file_is_left_to_the_folder_refresh(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    os.remove(path)
    watch._check()
    assert watch.reloads == []
