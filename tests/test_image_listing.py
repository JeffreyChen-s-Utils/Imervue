"""Tests for the folder listing the batch tools share."""
from __future__ import annotations

import os

from _hidden_attr import hide, windows_only

from Imervue.system.image_listing import list_images

_EXTS = {".png", ".jpg"}


def _touch(folder, *names):
    for name in names:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def _names(paths):
    return [os.path.basename(p) for p in paths]


def test_lists_only_the_wanted_extensions_in_any_case(tmp_path):
    _touch(tmp_path, "a.png", "b.JPG", "c.txt", "d.gif")
    assert _names(list_images(str(tmp_path), _EXTS)) == ["a.png", "b.JPG"]


def test_natural_name_order(tmp_path):
    _touch(tmp_path, "img10.png", "img2.png", "Img1.png")
    assert _names(list_images(str(tmp_path), _EXTS)) == ["Img1.png", "img2.png", "img10.png"]


def test_a_folder_named_like_an_image_is_not_listed(tmp_path):
    (tmp_path / "album.png").mkdir()
    _touch(tmp_path, "a.png")
    assert _names(list_images(str(tmp_path), _EXTS)) == ["a.png"]


def test_sub_folders_only_when_recursive(tmp_path):
    _touch(tmp_path, "top.png", "sub/inner.png")
    assert _names(list_images(str(tmp_path), _EXTS)) == ["top.png"]
    assert _names(list_images(str(tmp_path), _EXTS, recursive=True)) == ["inner.png", "top.png"]


def test_a_missing_folder_lists_nothing(tmp_path):
    missing = str(tmp_path / "nope")
    assert list_images(missing, _EXTS) == []
    assert list_images(missing, _EXTS, recursive=True) == []


def test_should_stop_ends_a_recursive_walk_early(tmp_path):
    _touch(tmp_path, "top.png", "sub/inner.png")
    asked = []

    def stop():
        asked.append(True)
        return len(asked) > 1   # let the first folder through, then stop

    assert _names(list_images(str(tmp_path), _EXTS, recursive=True, should_stop=stop)) == ["top.png"]


def test_extensions_can_be_any_iterable(tmp_path):
    _touch(tmp_path, "a.png")
    assert _names(list_images(str(tmp_path), [".png"])) == ["a.png"]


def test_hidden_files_and_mac_companions_are_left_out(tmp_path):
    _touch(tmp_path, "a.png", "._a.png", ".cover.png")
    assert _names(list_images(str(tmp_path), _EXTS)) == ["a.png"]


def test_a_recursive_walk_skips_hidden_folders(tmp_path):
    _touch(tmp_path, "a.png", ".Trashes/501/deleted.png", "sub/b.png", "sub/._b.png")
    assert _names(list_images(str(tmp_path), _EXTS, recursive=True)) == ["a.png", "b.png"]


@windows_only
def test_windows_hidden_files_and_folders_are_left_out(tmp_path):
    _touch(tmp_path, "a.png", "secret.png", "$RECYCLE.BIN/deleted.png")
    hide(tmp_path / "secret.png")
    hide(tmp_path / "$RECYCLE.BIN")
    assert _names(list_images(str(tmp_path), _EXTS)) == ["a.png"]
    assert _names(list_images(str(tmp_path), _EXTS, recursive=True)) == ["a.png"]


def test_a_hidden_folder_picked_on_purpose_is_listed(tmp_path):
    _touch(tmp_path, ".stash/a.png")
    assert _names(list_images(str(tmp_path / ".stash"), _EXTS)) == ["a.png"]
