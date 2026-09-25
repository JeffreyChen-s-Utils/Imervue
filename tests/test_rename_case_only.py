"""Changing only the case of a file name must work on a case-insensitive file system.

On Windows ``img.jpg`` → ``IMG.jpg`` saw ``IMG.jpg`` "already exist" (it is the
same file), so the file tree, Batch Rename and Token Rename all refused it.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from Imervue.system.file_transfer import is_same_file

_CASE_BLIND = os.path.normcase("A") == os.path.normcase("a")
case_blind_only = pytest.mark.skipif(not _CASE_BLIND, reason="the file system tells cases apart")


def _photo(tmp_path, name="img_0001.jpg"):
    path = tmp_path / name
    path.write_text("x", encoding="utf-8")
    return path


def test_is_same_file(tmp_path):
    a = _photo(tmp_path)
    b = _photo(tmp_path, "other.jpg")
    assert is_same_file(a, a) is True
    assert is_same_file(a, b) is False
    assert is_same_file(a, tmp_path / "missing.jpg") is False
    assert is_same_file(a, tmp_path / "IMG_0001.JPG") is _CASE_BLIND


@case_blind_only
def test_token_rename_changes_the_case(tmp_path):
    from Imervue.library.token_rename import apply_plan, preview
    src = _photo(tmp_path)
    plans = preview([str(src)], "IMG_0001.jpg")
    assert plans[0].conflict is False
    assert apply_plan(plans) == (1, 0)
    assert os.listdir(tmp_path) == ["IMG_0001.jpg"]


def test_token_rename_still_refuses_another_file(tmp_path):
    from Imervue.library.token_rename import preview
    src = _photo(tmp_path)
    _photo(tmp_path, "taken.jpg")
    assert preview([str(src)], "taken.jpg")[0].conflict is True


def test_token_rename_to_the_same_name_is_not_a_conflict(tmp_path):
    """dst != src compared strings, so a '/' vs '\' spelling of one path conflicted."""
    from Imervue.library.token_rename import preview
    src = _photo(tmp_path)
    assert preview([src.as_posix()], "img_0001.jpg")[0].conflict is False


@case_blind_only
def test_file_tree_rename_changes_the_case(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from Imervue.gui import file_tree_view as mod
    src = _photo(tmp_path)
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *_a, **_k: ("IMG_0001.jpg", True)))
    toasts = []
    tree = SimpleNamespace(
        _main_window=SimpleNamespace(toast=SimpleNamespace(
            warning=toasts.append, error=toasts.append, success=toasts.append)),
        _refresh_tree=lambda: None,
    )
    mod._FileTreeView._rename_path(tree, str(src))  # noqa: SLF001
    assert os.listdir(tmp_path) == ["IMG_0001.jpg"]
    assert toasts == ["Renamed to IMG_0001.jpg"]


@case_blind_only
def test_batch_rename_changes_the_case(qapp, tmp_path, monkeypatch):
    from Imervue.gpu_image_view.actions.batch_ops import BatchRenameDialog
    src = _photo(tmp_path)
    dialog = SimpleNamespace(_paths=[str(src)], _build_name=lambda _old, _i: "IMG_0001.jpg")
    renamed, failed = BatchRenameDialog._rename_all(dialog, 1)  # noqa: SLF001
    assert (len(renamed), failed) == (1, 0)
    assert os.listdir(tmp_path) == ["IMG_0001.jpg"]
