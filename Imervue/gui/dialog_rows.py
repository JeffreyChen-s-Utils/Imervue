"""Row builders shared by the batch and folder-based dialogs.

Each returns the layout plus the widgets the caller keeps a handle on, and
leaves file dialogs, visibility and persistence to the caller.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider

from Imervue.multi_language.language_wrapper import language_wrapper


def path_browse_row(
    on_browse: Callable[[], None], *, browse_text: str | None = None,
) -> tuple[QHBoxLayout, QLineEdit, QPushButton]:
    """Build ``stretching path edit | Browse…`` and return the row, edit and button.

    The Browse button calls ``on_browse``; ``browse_text`` overrides its
    default translated "Browse..." label.
    """
    if browse_text is None:
        browse_text = language_wrapper.language_word_dict.get("batch_convert_browse", "Browse...")
    row = QHBoxLayout()
    edit = QLineEdit()
    row.addWidget(edit, 1)
    browse = QPushButton(browse_text)
    browse.clicked.connect(on_browse)
    row.addWidget(browse)
    return row, edit, browse


def folder_picker_row(
    label: str, on_browse: Callable[[], None], *, browse_text: str | None = None,
) -> tuple[QHBoxLayout, QLineEdit]:
    """Build ``label | stretching path edit | Browse…`` and return the row and its edit.

    The Browse button calls ``on_browse``; the caller owns the file dialog and
    decides what to write into the edit. ``browse_text`` overrides the button's
    default translated "Browse..." label.
    """
    row, edit, _browse = path_browse_row(on_browse, browse_text=browse_text)
    row.insertWidget(0, QLabel(label))
    return row, edit


def quality_slider(lang: dict, value: int = 85) -> tuple[QLabel, QSlider]:
    """A "Quality: N" label and a 0–100 slider that keeps the label's number current."""
    prefix = lang.get("export_quality", "Quality:")
    label = QLabel(f"{prefix} {value}")
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(value)
    slider.valueChanged.connect(lambda v: label.setText(f"{prefix} {v}"))
    return label, slider


def action_button_row(*buttons: QPushButton) -> QHBoxLayout:
    """Right-align ``buttons`` in a row, in the order given."""
    row = QHBoxLayout()
    row.addStretch()
    for button in buttons:
        row.addWidget(button)
    return row
