"""Row builders and path pickers shared by the batch, folder and tool dialogs.

Each row builder returns the layout plus the widgets the caller keeps a handle
on; its Browse button only calls the caller's slot, which typically opens the
file dialog through ``save_path_into`` / ``open_path_into``. Visibility and
persistence stay with the caller.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QWidget,
)

from Imervue.gui.file_filters import image_filter
from Imervue.multi_language.language_wrapper import language_wrapper

def image_save_filter() -> str:
    """Save-dialog filter shared by the single-image tool dialogs that write PNG / JPEG / TIFF."""
    return image_filter(("png", "jpg", "tif"))


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


def save_path_into(
    parent: QWidget, edit: QLineEdit, title: str, file_filter: str,
    *, start: str | None = None,
) -> str | None:
    """Ask for a save path; a picked path replaces ``edit``'s text and is returned.

    The dialog starts at ``start`` when given, else at the edit's current text.
    It asks before picking an existing file. Returns None when cancelled.
    """
    directory = edit.text() if start is None else start
    path, _ = QFileDialog.getSaveFileName(parent, title, directory, file_filter)
    if not path:
        return None
    edit.setText(path)
    return path


def open_path_into(
    parent: QWidget, edit: QLineEdit, title: str, file_filter: str, *, start: str = "",
) -> None:
    """Ask for an existing file starting at ``start``; a picked path replaces ``edit``'s text."""
    path, _ = QFileDialog.getOpenFileName(parent, title, start, file_filter)
    if path:
        edit.setText(path)


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
