"""Tests for the bookmark dialog's JSON import."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from Imervue.gui import bookmark_dialog


@pytest.fixture
def messages(monkeypatch):
    shown = []
    monkeypatch.setattr(bookmark_dialog.QMessageBox, "information",
                        lambda *args: shown.append(("information", args[2])))
    monkeypatch.setattr(bookmark_dialog.QMessageBox, "warning",
                        lambda *args: shown.append(("warning", args[2])))
    return shown


def _import(monkeypatch, path):
    monkeypatch.setattr(bookmark_dialog.QFileDialog, "getOpenFileName",
                        lambda *_args, **_kwargs: (str(path), ""))
    bookmark_dialog.BookmarkDialog._import_json(SimpleNamespace(_refresh=lambda: None))  # noqa: SLF001


def test_a_file_saved_with_a_bom_imports(qapp, tmp_path, monkeypatch, messages):
    from Imervue.user_settings.bookmark import get_bookmarks
    path = tmp_path / "bookmarks.json"
    photo = str(tmp_path / "a.jpg")
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"bookmarks": [photo]}).encode("utf-8"))
    _import(monkeypatch, path)
    assert photo in get_bookmarks()
    assert messages == [("information", "Imported 1 new bookmark(s).")]


def test_bytes_that_are_not_utf8_are_reported(qapp, tmp_path, monkeypatch, messages):
    """UnicodeDecodeError escaped the handler instead of showing the warning."""
    path = tmp_path / "bookmarks.json"
    path.write_bytes(b"\xff\xfe{}")
    _import(monkeypatch, path)
    assert [kind for kind, _text in messages] == ["warning"]
