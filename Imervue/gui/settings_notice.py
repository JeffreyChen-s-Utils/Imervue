"""Tell the user at start-up that their settings file could not be read.

Imervue then runs on default settings, so every rating, tag and album seems
gone; without a word about why, the copy it keeps of the old file
(:func:`Imervue.user_settings.user_setting_dict.unreadable_settings_file`)
would never be found.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import unreadable_settings_file


def warn_if_settings_unreadable(parent: QWidget | None) -> QMessageBox | None:
    """Show a non-blocking warning when the settings file could not be read; returns the box.

    The box deletes itself when closed. Returns None when there is nothing
    to tell.
    """
    path = unreadable_settings_file()
    if path is None:
        return None
    lang = language_wrapper.language_word_dict
    text = lang.get(
        "settings_unreadable",
        "Imervue could not read its settings file:\n{path}\n\nIt started with default "
        "settings. Before the file is saved over, a copy is kept next to it as "
        "{name}.unreadable-<date>-<time>. To get your earlier settings back, quit "
        "Imervue and rename that copy to {name}.",
    ).format(path=path, name=path.name)
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        lang.get("settings_unreadable_title", "Settings could not be read"),
        text, QMessageBox.StandardButton.Ok, parent)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.open()
    return box
