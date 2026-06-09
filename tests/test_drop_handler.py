"""Tests for drop_handler — drag-and-drop file/folder opening."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.gpu_image_view import drop_handler


class _FakeUrl:
    def __init__(self, path, is_local=True):
        self._path = path
        self._is_local = is_local

    def isLocalFile(self):
        return self._is_local

    def toLocalFile(self):
        return self._path


class _FakeMime:
    def __init__(self, urls):
        self._urls = urls

    def urls(self):
        return self._urls


class _FakeEvent:
    def __init__(self, urls):
        self._mime = _FakeMime(urls)
        self.accepted = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True


def _make_view():
    mw = SimpleNamespace(
        language_wrapper=SimpleNamespace(language_word_dict={}),
        model=SimpleNamespace(setRootPath=lambda p: None, index=lambda p: p),
        tree=SimpleNamespace(setRootIndex=lambda i: None),
        filename_label=SimpleNamespace(setText=lambda t: None),
        watch_folder=lambda p: None,
    )
    return SimpleNamespace(main_window=mw, cleared=False, clear_tile_grid=lambda: None)


@pytest.fixture(autouse=True)
def _patch_side_effects(monkeypatch):
    monkeypatch.setattr(
        "Imervue.gpu_image_view.images.image_loader.open_path",
        lambda main_gui, path: None,
    )
    monkeypatch.setattr(
        "Imervue.user_settings.recent_image.add_recent_folder", lambda p: None
    )
    monkeypatch.setattr(
        "Imervue.user_settings.recent_image.add_recent_image", lambda p: None
    )
    monkeypatch.setattr(
        "Imervue.menu.recent_menu.rebuild_recent_menu", lambda mw: None
    )


def test_no_urls_is_noop():
    event = _FakeEvent([])
    drop_handler.handle_drop(_make_view(), event)
    assert event.accepted is False


def test_no_local_files_is_noop():
    event = _FakeEvent([_FakeUrl("http://x", is_local=False)])
    drop_handler.handle_drop(_make_view(), event)
    assert event.accepted is False


def test_drop_folder_accepts(monkeypatch, tmp_path):
    folder = tmp_path / "imgs"
    folder.mkdir()
    event = _FakeEvent([_FakeUrl(str(folder))])
    drop_handler.handle_drop(_make_view(), event)
    assert event.accepted is True


def test_drop_file_accepts(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    event = _FakeEvent([_FakeUrl(str(f))])
    drop_handler.handle_drop(_make_view(), event)
    assert event.accepted is True
