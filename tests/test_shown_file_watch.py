"""Tests for reloading the deep-zoom picture when another program rewrites its file."""
from __future__ import annotations

import os

import pytest

from Imervue.gpu_image_view import shown_file_watch
from Imervue.gpu_image_view.shown_file_watch import ShownFileWatch


@pytest.fixture
def watch(qapp, monkeypatch):
    """A watch polling every 20 ms whose picture is always on screen, recording each reload."""
    monkeypatch.setattr(shown_file_watch, "POLL_MS", 20)
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


def _measure_twice(watch) -> None:
    """Two polls: the first sees the change, the second that it held still."""
    watch._tick()
    watch._tick()


def test_follow_polls_the_file_and_none_stops(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    assert watch.path == path
    assert watch.polling
    watch.follow(None)
    assert watch.path is None
    assert not watch.polling


def test_following_another_picture_measures_that_one(watch, tmp_path):
    first, second = _picture(tmp_path, "a.png"), _picture(tmp_path, "b.png")
    watch.follow(first)
    watch.follow(second)
    (tmp_path / "a.png").write_bytes(b"y" * 300)
    _measure_twice(watch)
    assert watch.reloads == []


def test_a_missing_file_is_not_polled(watch, tmp_path):
    watch.follow(str(tmp_path / "gone.png"))
    assert not watch.polling
    _measure_twice(watch)
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


def test_another_programs_rename_over_the_file_is_never_refused(watch, qapp, tmp_path):
    """A file QFileSystemWatcher watched refused about one rename-over save in ten on Windows."""
    path = _picture(tmp_path)
    watch.follow(path)
    copy = tmp_path / "a.png.tmp"
    for i in range(200):
        copy.write_bytes(bytes([i % 256]) * 300)
        os.replace(copy, path)   # PermissionError under a Qt file watch
        qapp.processEvents()
        watch._tick()


def test_a_file_still_being_written_waits_until_it_holds_still(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    with open(path, "ab") as handle:
        handle.write(b"first half")
        watch._tick()                 # the first poll sees it growing
        assert watch.reloads == []
        handle.write(b"second half")
    watch._tick()                     # still moving
    assert watch.reloads == []
    watch._tick()                     # held still for one poll
    assert watch.reloads == [path]


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
    watch.follow(_picture(tmp_path))
    _measure_twice(watch)
    assert watch.reloads == []


def test_a_save_that_keeps_the_old_time_is_seen_by_its_size(watch, tmp_path):
    """Qt on Windows compared the modification time alone, so such a save sent nothing."""
    path = _picture(tmp_path)
    watch.follow(path)
    stamp = os.stat(path).st_mtime
    with open(path, "r+b") as handle:
        handle.write(b"y" * 300)
    os.utime(path, (stamp, stamp))   # a tool that preserves file dates
    _measure_twice(watch)
    assert watch.reloads == [path]


def test_a_picture_no_longer_shown_is_not_reloaded(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    (tmp_path / "a.png").write_bytes(b"y" * 300)
    watch.shown["yes"] = False
    _measure_twice(watch)
    assert watch.reloads == []


def test_a_removed_file_is_left_to_the_folder_refresh(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    os.remove(path)
    _measure_twice(watch)
    assert watch.reloads == []


def test_a_file_removed_and_written_again_reloads(watch, tmp_path):
    path = _picture(tmp_path)
    watch.follow(path)
    os.remove(path)
    _measure_twice(watch)
    _picture(tmp_path, size=300)
    _measure_twice(watch)
    assert watch.reloads == [path]
