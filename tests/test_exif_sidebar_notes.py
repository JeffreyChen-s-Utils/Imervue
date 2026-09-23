"""The EXIF sidebar's notes field reports a library-index failure instead of hiding it.

Driven on ``_load_note_for`` / ``_flush_note`` unbound on a fake, so no widget
is built. A locked or unwritable index (``sqlite3.Error`` / ``OSError``) is
logged and the field falls back to empty; anything else is a bug and propagates.
"""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from Imervue.gui.exif_sidebar import ExifSidebar
from Imervue.library import image_index


class _Edit:
    def __init__(self, text=""):
        self.text = text

    def blockSignals(self, _blocked):  # noqa: N802 - mirrors Qt's camelCase API
        return False

    def setPlainText(self, text):  # noqa: N802 - mirrors Qt's camelCase API
        self.text = text

    def toPlainText(self):  # noqa: N802 - mirrors Qt's camelCase API
        return self.text


def _sidebar(text=""):
    return SimpleNamespace(_notes_edit=_Edit(text), _notes_current_path="a.png",
                           _notes_save_timer=SimpleNamespace(isActive=lambda: False))


def _raise(exc):
    def _fail(*_args):
        raise exc
    return _fail


def test_flush_saves_the_note(monkeypatch):
    saved = []
    monkeypatch.setattr(image_index, "set_note", lambda path, note: saved.append((path, note)))
    ExifSidebar._flush_note(_sidebar("sunset"))
    assert saved == [("a.png", "sunset")]


def test_failed_save_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(image_index, "set_note", _raise(sqlite3.OperationalError("database is locked")))
    with caplog.at_level("DEBUG", logger="Imervue"):
        ExifSidebar._flush_note(_sidebar("sunset"))
    (record,) = caplog.records
    assert "Could not save the note for a.png" in record.getMessage()
    assert record.exc_info[0] is sqlite3.OperationalError


def test_failed_load_is_logged_and_shows_empty(monkeypatch, caplog):
    monkeypatch.setattr(image_index, "get_note", _raise(OSError("disk gone")))
    sidebar = _sidebar("stale")
    with caplog.at_level("DEBUG", logger="Imervue"):
        ExifSidebar._load_note_for(sidebar, "b.png")
    assert sidebar._notes_edit.text == ""
    (record,) = caplog.records
    assert "Could not read the note for b.png" in record.getMessage()


def test_unexpected_save_error_propagates(monkeypatch):
    monkeypatch.setattr(image_index, "set_note", _raise(TypeError("bad note")))
    with pytest.raises(TypeError):
        ExifSidebar._flush_note(_sidebar("sunset"))
