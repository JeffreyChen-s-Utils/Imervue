"""Profile manager — switch / create / rename / delete profiles.

Each profile owns its own ``user_setting_dict`` entries: language,
recents, bookmarks, ratings, develop overrides, … The dialog is a small
list view with action buttons; profile mutations route through
``user_setting_dict`` so persistence stays atomic and the new state
takes effect immediately for any subsequent save.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import (
    DEFAULT_PROFILE,
    create_profile,
    current_profile,
    delete_profile,
    list_profiles,
    rename_profile,
    switch_profile,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.profiles_dialog")


class ProfilesDialog(QDialog):
    """Switch / add / rename / delete user-setting profiles."""

    def __init__(self, parent: ImervueMainWindow | None = None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("profiles_title", "Profiles"))
        self.setModal(True)
        self.resize(420, 360)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list, stretch=1)
        layout.addLayout(self._build_buttons(lang))

        self._refresh()

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        for label_key, fallback, slot in (
            ("profiles_switch", "Switch to", self._switch),
            ("profiles_add", "Add…", self._add),
            ("profiles_rename", "Rename…", self._rename),
            ("profiles_delete", "Delete", self._delete),
        ):
            btn = QPushButton(lang.get(label_key, fallback))
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        close_btn = QPushButton(lang.get("close", "Close"))
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        return row

    # ------------------------------------------------------------------
    # State refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        active = current_profile()
        for name in list_profiles():
            label = name + (
                f"  {language_wrapper.language_word_dict.get('profiles_active_marker', '(active)')}"
                if name == active else ""
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_double_click(self, _item: QListWidgetItem) -> None:
        self._switch()

    def _switch(self) -> None:
        name = self._selected_name()
        if not name or name == current_profile():
            return
        if switch_profile(name):
            self._refresh()
            self._notify(
                "profiles_switched",
                "Switched to profile '{name}'. Restart for full effect.",
                name=name,
            )

    def _add(self) -> None:
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("profiles_add", "Add"),
            lang.get("profiles_new_name", "New profile name:"),
        )
        if not ok or not name.strip():
            return
        if create_profile(name.strip()):
            self._refresh()
            self._notify(
                "profiles_created", "Profile '{name}' created.", name=name.strip(),
            )
        else:
            self._show_error(lang.get(
                "profiles_create_failed",
                "Could not create that profile (duplicate or empty name).",
            ))

    def _rename(self) -> None:
        old = self._selected_name()
        if not old:
            return
        lang = language_wrapper.language_word_dict
        new, ok = QInputDialog.getText(
            self,
            lang.get("profiles_rename", "Rename"),
            lang.get("profiles_new_name", "New profile name:"),
            text=old,
        )
        if not ok or not new.strip() or new.strip() == old:
            return
        if rename_profile(old, new.strip()):
            self._refresh()
        else:
            self._show_error(lang.get(
                "profiles_rename_failed",
                "Could not rename (duplicate or invalid name).",
            ))

    def _delete(self) -> None:
        name = self._selected_name()
        if not name:
            return
        lang = language_wrapper.language_word_dict
        if name == current_profile() or name == DEFAULT_PROFILE:
            self._show_error(lang.get(
                "profiles_cannot_delete_protected",
                "You cannot delete the default or active profile.",
            ))
            return
        confirm = QMessageBox.question(
            self,
            lang.get("profiles_delete", "Delete"),
            lang.get(
                "profiles_delete_confirm",
                "Permanently delete profile '{name}'? This cannot be undone.",
            ).format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if delete_profile(name):
            self._refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(
            self,
            language_wrapper.language_word_dict.get("profiles_title", "Profiles"),
            message,
        )

    def _notify(self, key: str, fallback: str, **kwargs) -> None:
        parent = self.parent()
        if parent is None or not hasattr(parent, "toast"):
            return
        msg = language_wrapper.language_word_dict.get(key, fallback).format(**kwargs)
        parent.toast.info(msg)


def open_profiles_dialog(parent: ImervueMainWindow | None = None) -> None:
    ProfilesDialog(parent).exec()
