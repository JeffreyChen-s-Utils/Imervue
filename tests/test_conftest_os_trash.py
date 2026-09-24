"""Tests for the autouse ``os_trash`` fixture in ``tests/conftest.py``.

Delete tests rely on it behaving like ``send2trash`` for the calls the product
code makes, and on it never touching the OS Recycle Bin.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _touch(path: Path) -> str:
    path.write_bytes(b"x")
    return str(path)


def test_product_imports_get_the_fake(os_trash, tmp_path):
    from send2trash import send2trash
    target = _touch(tmp_path / "a.png")
    send2trash(target)
    assert os_trash == [target]
    assert not Path(target).exists()


def test_accepts_a_list_and_pathlike(os_trash, tmp_path):
    from send2trash import send2trash
    a, b = _touch(tmp_path / "a.png"), tmp_path / "b.png"
    _touch(b)
    send2trash([a, b])
    assert os_trash == [a, str(b)]
    assert not Path(a).exists() and not b.exists()


def test_single_pathlike(os_trash, tmp_path):
    from send2trash import send2trash
    target = tmp_path / "c.png"
    _touch(target)
    send2trash(target)
    assert os_trash == [str(target)]


def test_removes_a_directory_tree(os_trash, tmp_path):
    from send2trash import send2trash
    folder = tmp_path / "album"
    (folder / "nested").mkdir(parents=True)
    _touch(folder / "nested" / "x.png")
    send2trash(str(folder))
    assert not folder.exists()
    assert os_trash == [str(folder)]


def test_missing_path_raises_and_stops_the_batch(os_trash, tmp_path):
    from send2trash import send2trash
    kept = _touch(tmp_path / "kept.png")
    with pytest.raises(FileNotFoundError):
        send2trash([str(tmp_path / "gone.png"), kept])
    assert os_trash == []
    assert Path(kept).exists()


def test_empty_batch_is_a_no_op(os_trash):
    from send2trash import send2trash
    send2trash([])
    assert os_trash == []


def test_trash_batch_goes_through_the_fake(os_trash, tmp_path):
    from Imervue.system.trash_ops import trash_batch
    paths = [_touch(tmp_path / f"{i}.png") for i in range(3)]
    trashed, failed = trash_batch(paths)
    assert sorted(trashed) == sorted(paths)
    assert failed == []
    assert sorted(os_trash) == sorted(paths)


def test_keyboard_send_to_trash_goes_through_the_fake(os_trash, tmp_path):
    from Imervue.gpu_image_view.actions.keyboard_actions import _send_to_trash
    target = _touch(tmp_path / "k.png")
    assert _send_to_trash(target) is True
    assert os_trash == [target]


def test_stand_in_module_when_send2trash_is_missing(monkeypatch, tmp_path):
    """Re-running the fixture body with the package unimportable installs a stand-in."""
    import builtins
    import sys

    import conftest

    real_import = builtins.__import__

    def _no_send2trash(name, *args, **kwargs):
        if name == "send2trash":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "send2trash", raising=False)
    monkeypatch.setattr(builtins, "__import__", _no_send2trash)
    trashed = conftest.os_trash.__wrapped__(monkeypatch)
    monkeypatch.setattr(builtins, "__import__", real_import)
    from send2trash import send2trash
    target = _touch(tmp_path / "s.png")
    send2trash(target)
    assert trashed == [target]
