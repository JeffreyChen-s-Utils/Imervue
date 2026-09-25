"""Tests for which files a folder listing treats as hidden."""
from __future__ import annotations

import os

import pytest
from _hidden_attr import hide, windows_only

from Imervue.system import hidden_files
from Imervue.system.hidden_files import is_hidden


def _entry(folder, name):
    with os.scandir(folder) as entries:
        return next(entry for entry in entries if entry.name == name)


@pytest.mark.parametrize("name", ["._photo.jpg", ".cover.png", ".Trashes"])
def test_a_name_starting_with_a_dot_is_hidden(tmp_path, name):
    (tmp_path / name).write_bytes(b"x")
    assert is_hidden(str(tmp_path / name))
    assert is_hidden(tmp_path / name)
    assert is_hidden(_entry(tmp_path, name))


def test_a_plain_file_is_not_hidden(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    assert not is_hidden(str(tmp_path / "photo.jpg"))
    assert not is_hidden(_entry(tmp_path, "photo.jpg"))


@windows_only
@pytest.mark.parametrize("folder", [False, True])
def test_windows_hidden_attribute_hides_a_file_or_folder(tmp_path, folder):
    path = tmp_path / "secret"
    if folder:
        path.mkdir()
    else:
        path.write_bytes(b"x")
    hide(path)
    assert is_hidden(str(path))
    assert is_hidden(_entry(tmp_path, "secret"))


def test_a_file_that_cannot_be_read_is_not_hidden(tmp_path):
    assert not is_hidden(str(tmp_path / "gone.jpg"))


def test_elsewhere_only_the_dot_counts(tmp_path, monkeypatch):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    monkeypatch.setattr(hidden_files.sys, "platform", "linux")

    def no_stat(*_args, **_kwargs):
        raise AssertionError("no attribute to read off Windows")

    monkeypatch.setattr(hidden_files.os, "stat", no_stat)
    assert not is_hidden(str(tmp_path / "photo.jpg"))
    assert is_hidden(str(tmp_path / ".photo.jpg"))
