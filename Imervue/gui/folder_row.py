"""Label + path edit + Browse button row shared by the folder-based dialogs."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton

from Imervue.multi_language.language_wrapper import language_wrapper


def folder_picker_row(
    label: str, on_browse: Callable[[], None],
) -> tuple[QHBoxLayout, QLineEdit]:
    """Build ``label | stretching path edit | Browse…`` and return the row and its edit.

    The Browse button calls ``on_browse``; the caller owns the file dialog and
    decides what to write into the edit.
    """
    lang = language_wrapper.language_word_dict
    row = QHBoxLayout()
    row.addWidget(QLabel(label))
    edit = QLineEdit()
    row.addWidget(edit, 1)
    browse = QPushButton(lang.get("batch_convert_browse", "Browse..."))
    browse.clicked.connect(on_browse)
    row.addWidget(browse)
    return row, edit
