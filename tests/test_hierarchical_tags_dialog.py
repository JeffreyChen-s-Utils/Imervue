"""Tests for the hierarchical tags dialog's delete confirmation."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from Imervue.gui import hierarchical_tags_dialog as mod
from Imervue.library import image_index


@pytest.fixture
def dialog(qapp, monkeypatch):
    image_index.add_image_tag("C:/a.png", "animal/cat/british")
    dlg = mod.HierarchicalTagsDialog(None)
    monkeypatch.setattr(dlg, "_selected_tag_path", lambda: "animal/cat")
    yield dlg
    dlg.deleteLater()


@pytest.fixture
def asked(monkeypatch):
    """Record each question and answer it with ``asked.answer``."""
    calls: list[tuple] = []

    def question(_parent, title, text, buttons, default):
        calls.append((title, text, buttons, default))
        return asked_answer[0]

    asked_answer = [QMessageBox.StandardButton.No]
    monkeypatch.setattr(mod.QMessageBox, "question", question)
    return calls, asked_answer


def _tags():
    return image_index.tags_of_image("C:/a.png")


def test_deleting_a_branch_asks_in_the_dictionarys_words_with_no_as_the_default(dialog, asked):
    calls, _answer = asked
    dialog._delete_tag()
    ((title, text, buttons, default),) = calls
    assert title == "Delete"
    assert "animal/cat" in text and "every tag under it" in text
    assert buttons == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    assert default == QMessageBox.StandardButton.No
    assert _tags() == ["animal/cat/british"]   # the answer was No: nothing went


def test_yes_deletes_the_branch(dialog, asked):
    _calls, answer = asked
    answer[0] = QMessageBox.StandardButton.Yes
    dialog._delete_tag()
    assert _tags() == []
