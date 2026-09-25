"""Tests for reloading the deep-zoom picture when another program rewrites its file."""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt

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


def _dated_after(target, previous) -> None:
    """Give *target* a modification time 2 s after *previous*'s, as a real later save has.

    Qt on Windows tells a changed file by its modification time alone, and two
    writes inside one tick of the system clock (up to 15.6 ms) share it: a test
    that saves straight after creating the file would go unnoticed.
    """
    stamp = os.stat(previous).st_mtime + 2
    os.utime(target, (stamp, stamp))


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
    _dated_after(path, path)
    assert pump_until(lambda: watch.reloads == [path])


def test_a_copy_renamed_over_the_file_reloads(watch, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    copy = tmp_path / "a.png.tmp"
    copy.write_bytes(b"z" * 300)
    _dated_after(copy, path)
    os.replace(copy, path)
    assert pump_until(lambda: watch.reloads == [path])


def test_a_second_rewrite_reloads_again(watch, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    with open(path, "r+b") as handle:
        handle.write(b"y" * 300)
    _dated_after(path, path)
    assert pump_until(lambda: len(watch.reloads) == 1)
    with open(path, "ab") as handle:
        handle.write(b"more")
    _dated_after(path, path)
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


def test_coming_back_to_the_front_catches_a_save_that_kept_the_old_time(watch, qapp, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    watch._watcher.removePaths(watch._watcher.files())   # Qt misses this save
    stamp = os.stat(path).st_mtime
    with open(path, "r+b") as handle:
        handle.write(b"y" * 300)
    os.utime(path, (stamp, stamp))   # a tool that preserves file dates
    qapp.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)
    assert pump_until(lambda: watch.reloads == [path])


def test_coming_back_with_nothing_changed_reloads_nothing(watch, qapp, tmp_path, pump_until):
    path = _picture(tmp_path)
    watch.follow(path)
    qapp.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)
    assert watch._settle.isActive()
    assert pump_until(lambda: not watch._settle.isActive())
    assert watch.reloads == []


def test_going_to_the_background_or_watching_nothing_measures_nothing(watch, qapp, tmp_path):
    qapp.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)
    assert not watch._settle.isActive()   # no picture followed
    watch.follow(_picture(tmp_path))
    qapp.applicationStateChanged.emit(Qt.ApplicationState.ApplicationInactive)
    assert not watch._settle.isActive()
