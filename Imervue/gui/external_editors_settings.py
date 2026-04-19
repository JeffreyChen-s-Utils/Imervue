"""External editor configuration dialog — add / edit / remove entries."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, QFormLayout,
)

from Imervue.external.editors import EditorEntry, load_editors, save_editors
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.external_editors_settings")


def open_external_editors_settings(ui: ImervueMainWindow) -> None:
    dlg = ExternalEditorsDialog(ui)
    dlg.exec()


class ExternalEditorsDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self.ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("ext_editor_title", "External Editors"))
        self.setMinimumSize(520, 380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "ext_editor_help",
            "Configure programs you can launch on the current image.",
        )))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list, stretch=1)

        # Editor form — name, executable (with Browse), extra args
        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._exe_edit = QLineEdit()
        self._args_edit = QLineEdit()
        self._args_edit.setPlaceholderText("{path}")

        browse_row = QHBoxLayout()
        browse_row.addWidget(self._exe_edit, stretch=1)
        browse_btn = QPushButton(lang.get("ext_editor_browse", "Browse\u2026"))
        browse_btn.clicked.connect(self._browse_exe)
        browse_row.addWidget(browse_btn)
        browse_container = QHBoxLayout()
        browse_container.addLayout(browse_row)

        form.addRow(lang.get("ext_editor_name", "Name"), self._name_edit)
        form.addRow(lang.get("ext_editor_exe", "Executable"), browse_row)
        form.addRow(lang.get("ext_editor_args", "Arguments"), self._args_edit)
        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton(lang.get("ext_editor_add", "Add"))
        add_btn.clicked.connect(self._add_entry)
        btn_row.addWidget(add_btn)

        update_btn = QPushButton(lang.get("ext_editor_update", "Update"))
        update_btn.clicked.connect(self._update_entry)
        btn_row.addWidget(update_btn)

        remove_btn = QPushButton(lang.get("ext_editor_remove", "Remove"))
        remove_btn.clicked.connect(self._remove_entry)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        close_btn = QPushButton(lang.get("ext_editor_close", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._entries: list[EditorEntry] = load_editors()
        self._refresh_list()

    # ------------------------------------------------------------------
    def _refresh_list(self) -> None:
        self._list.clear()
        for entry in self._entries:
            self._list.addItem(QListWidgetItem(f"{entry.name}  —  {entry.executable}"))

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            self._name_edit.setText(entry.name)
            self._exe_edit.setText(entry.executable)
            self._args_edit.setText(entry.arguments)

    def _browse_exe(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("ext_editor_browse_title", "Select editor executable"),
        )
        if path:
            self._exe_edit.setText(path)

    def _build_from_form(self) -> EditorEntry | None:
        entry = EditorEntry.from_dict({
            "name": self._name_edit.text(),
            "executable": self._exe_edit.text(),
            "arguments": self._args_edit.text(),
        })
        if entry is None:
            lang = language_wrapper.language_word_dict
            QMessageBox.warning(
                self,
                lang.get("ext_editor_title", "External Editors"),
                lang.get("ext_editor_invalid", "Name and executable are required."),
            )
        return entry

    def _add_entry(self) -> None:
        entry = self._build_from_form()
        if entry is None:
            return
        self._entries.append(entry)
        save_editors(self._entries)
        self._refresh_list()

    def _update_entry(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        entry = self._build_from_form()
        if entry is None:
            return
        self._entries[row] = entry
        save_editors(self._entries)
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _remove_entry(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        del self._entries[row]
        save_editors(self._entries)
        self._refresh_list()
