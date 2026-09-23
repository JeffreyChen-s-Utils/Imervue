"""Tests for ``Imervue.gui.folder_row.folder_picker_row``."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QWidget

from Imervue.gui import folder_row
from Imervue.gui.folder_row import folder_picker_row


def _hosted(row):
    host = QWidget()
    host.setLayout(row)
    return host


def test_row_holds_label_stretching_edit_and_browse(qapp, monkeypatch):
    monkeypatch.setattr(folder_row.language_wrapper, "language_word_dict", {})
    row, edit = folder_picker_row("Source:", lambda: None)
    host = _hosted(row)
    try:
        label, line_edit, browse = (row.itemAt(i).widget() for i in range(row.count()))
        assert isinstance(label, QLabel) and label.text() == "Source:"
        assert line_edit is edit and isinstance(edit, QLineEdit)
        assert isinstance(browse, QPushButton) and browse.text() == "Browse..."
        assert [row.stretch(i) for i in range(3)] == [0, 1, 0]
    finally:
        host.deleteLater()


def test_browse_button_calls_back(qapp):
    calls = []
    row, _edit = folder_picker_row("Out:", lambda: calls.append(True))
    host = _hosted(row)
    try:
        row.itemAt(2).widget().click()
        row.itemAt(2).widget().click()
        assert calls == [True, True]
    finally:
        host.deleteLater()


def test_browse_label_is_translated(qapp, monkeypatch):
    monkeypatch.setattr(folder_row.language_wrapper, "language_word_dict",
                        {"batch_convert_browse": "瀏覽..."})
    row, _edit = folder_picker_row("", lambda: None)
    host = _hosted(row)
    try:
        assert row.itemAt(2).widget().text() == "瀏覽..."
        assert row.itemAt(0).widget().text() == ""
    finally:
        host.deleteLater()


def test_browse_text_override(qapp, monkeypatch):
    monkeypatch.setattr(folder_row.language_wrapper, "language_word_dict",
                        {"batch_convert_browse": "unused"})
    row, _edit = folder_picker_row("Src:", lambda: None, browse_text="Pick…")
    host = _hosted(row)
    try:
        assert row.itemAt(2).widget().text() == "Pick…"
    finally:
        host.deleteLater()
