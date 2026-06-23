"""Controlled-vocabulary editor — edit the structured keyword text and save.

The vocabulary is tab-indented (one tab per level) with brace synonyms, e.g.::

    animal
    \tdog
    \t\tLabrador {lab} {lab retriever}

Parsing / expansion live in :mod:`library.keyword_vocabulary`; this is the Qt
shell that loads and saves the text through ``keyword_vocabulary_store``.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.library.keyword_vocabulary_store import (
    get_vocabulary_text,
    set_vocabulary_text,
)
from Imervue.multi_language.language_wrapper import language_wrapper

_HELP = (
    "One keyword per line; indent with tabs to nest; put synonyms after the "
    "name in curly braces."
)


class KeywordVocabularyDialog(QDialog):
    """Edit the stored controlled vocabulary as structured-keyword text."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("vocab_title", "Keyword Vocabulary"))
        self.setMinimumSize(460, 380)

        self._editor = QPlainTextEdit(get_vocabulary_text())
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("vocab_help", _HELP)))
        layout.addWidget(self._editor)
        layout.addLayout(self._build_buttons(lang))

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(lang.get("export_save", "Save"))
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        return row

    def _save(self) -> None:
        from Imervue.user_settings.user_setting_dict import schedule_save
        set_vocabulary_text(self._editor.toPlainText())
        schedule_save()
        self.accept()


def open_keyword_vocabulary(parent: QWidget | None = None) -> None:
    KeywordVocabularyDialog(parent).exec()
