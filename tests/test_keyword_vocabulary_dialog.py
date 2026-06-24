"""Smoke tests for the keyword-vocabulary editor dialog."""
from __future__ import annotations

from Imervue.gui.keyword_vocabulary_dialog import KeywordVocabularyDialog
from Imervue.library.keyword_vocabulary_store import (
    get_vocabulary_text,
    set_vocabulary_text,
)


def test_dialog_loads_stored_text(qapp):
    set_vocabulary_text("animal\n\tdog\n")
    dlg = KeywordVocabularyDialog()  # parent=None keeps qapp teardown clean
    assert dlg._editor.toPlainText() == "animal\n\tdog\n"


def test_dialog_save_persists_text(qapp):
    dlg = KeywordVocabularyDialog()
    dlg._editor.setPlainText("cat\n\tsiamese {meezer}\n")
    dlg._save()
    assert get_vocabulary_text() == "cat\n\tsiamese {meezer}\n"
