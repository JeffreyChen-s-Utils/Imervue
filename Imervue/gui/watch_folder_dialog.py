"""Watched-folder automation dialog.

Pick a folder and a develop preset; while watching, every new image dropped
into the folder gets that preset assigned (non-destructively, through the
recipe store) — a hands-off ingest pipeline. The detection / dispatch logic
lives in :mod:`Imervue.system.watch_folder`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.develop_presets import DevelopPresetStore, apply_recipe_to_paths
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.watch_folder import WatchFolderService
from Imervue.user_settings.user_setting_dict import user_setting_dict

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class WatchFolderDialog(QDialog):
    """Start/stop watching a folder and auto-apply a develop preset."""

    def __init__(self, viewer: GPUImageView, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._preset_store = DevelopPresetStore(user_setting_dict)
        self._service = WatchFolderService(self._process, parent=self)
        self._service.processed.connect(self._on_processed)
        self._count = 0
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("watch_folder_title", "Watched Folder"))
        self.setMinimumWidth(460)
        self._build_ui(lang)

    def _build_ui(self, lang: dict) -> None:
        self._folder_edit = QLineEdit()
        browse = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        browse.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel(lang.get("duplicate_source", "Source folder:")))
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(browse)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(self._preset_store.names())

        self._toggle = QPushButton(lang.get("watch_folder_start", "Start Watching"))
        self._toggle.clicked.connect(self._toggle_watching)
        self._status = QLabel("")

        layout = QVBoxLayout(self)
        layout.addLayout(folder_row)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(lang.get("watch_folder_preset", "Apply preset:")))
        preset_row.addWidget(self._preset_combo, 1)
        layout.addLayout(preset_row)
        layout.addWidget(self._toggle)
        layout.addWidget(self._status)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self)
        if folder:
            self._folder_edit.setText(folder)

    def _toggle_watching(self) -> None:
        lang = language_wrapper.language_word_dict
        if self._service.root:
            self._service.stop()
            self._toggle.setText(lang.get("watch_folder_start", "Start Watching"))
            self._status.setText("")
            return
        self._count = 0
        if self._service.start(self._folder_edit.text().strip()):
            self._toggle.setText(lang.get("watch_folder_stop", "Stop Watching"))
            self._update_status()
        else:
            self._status.setText(
                lang.get("watch_folder_unavailable", "Could not watch this folder."))

    def _process(self, path: str) -> None:
        name = self._preset_combo.currentText()
        recipe = self._preset_store.get(name)
        if recipe is not None:
            apply_recipe_to_paths(recipe, [path], recipe_store)

    def _on_processed(self, count: int) -> None:
        self._count += count
        self._update_status()

    def _update_status(self) -> None:
        lang = language_wrapper.language_word_dict
        self._status.setText(
            lang.get("watch_folder_watching", "Watching {path} — {n} processed").format(
                path=self._service.root, n=self._count))

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._service.stop()
        super().closeEvent(event)


def open_watch_folder(viewer: GPUImageView) -> None:
    WatchFolderDialog(viewer).exec()
