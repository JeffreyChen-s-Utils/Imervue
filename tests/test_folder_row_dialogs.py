"""The source-folder row of the folder-based dialogs.

Pins, for each dialog, the row's position, label, path edit and Browse button,
and that a picked folder lands in the edit while a cancelled pick leaves it
alone — the contract ``Imervue.gui.folder_row.folder_picker_row`` has to keep
when the dialogs build the row through it.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QFileDialog, QLabel, QLineEdit, QPushButton

from Imervue.multi_language.language_wrapper import language_wrapper


def _duplicate():
    from Imervue.gui.duplicate_detection_dialog import DuplicateDetectionDialog
    return DuplicateDetectionDialog(SimpleNamespace(main_window=None)), "_folder_edit"


def _exif_strip():
    from Imervue.gui.exif_strip_dialog import ExifStripDialog
    return ExifStripDialog(SimpleNamespace(main_window=None)), "_src_edit"


def _watch_folder():
    from Imervue.gui.watch_folder_dialog import WatchFolderDialog
    return WatchFolderDialog(object()), "_folder_edit"


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})


@pytest.mark.parametrize("factory", [_duplicate, _exif_strip, _watch_folder])
def test_source_row_is_first_and_browse_fills_it(qapp, monkeypatch, factory):
    dialog, edit_attr = factory()
    try:
        row = dialog.layout().itemAt(0).layout()
        label, edit, browse = (row.itemAt(i).widget() for i in range(row.count()))
        assert isinstance(label, QLabel) and label.text() == "Source folder:"
        assert isinstance(edit, QLineEdit) and edit is getattr(dialog, edit_attr)
        assert isinstance(browse, QPushButton) and browse.text() == "Browse..."
        assert [row.stretch(i) for i in range(3)] == [0, 1, 0]

        picks = iter(["/picked", ""])
        monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *_a, **_k: next(picks)))
        browse.click()
        assert edit.text() == "/picked"
        browse.click()
        assert edit.text() == "/picked"
    finally:
        dialog.deleteLater()
