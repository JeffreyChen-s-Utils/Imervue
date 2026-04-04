"""Bookmark manager dialog — browse and manage cross-folder image collections."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.bookmark import get_bookmarks, remove_bookmark, clear_bookmarks

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def open_bookmark_dialog(main_gui: GPUImageView):
    dlg = BookmarkDialog(main_gui)
    dlg.exec()


class BookmarkDialog(QDialog):
    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui)
        self.main_gui = main_gui
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("bookmark_title", "Bookmarks"))
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Count label
        self._count_label = QLabel()
        layout.addWidget(self._count_label)

        # List
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        # Buttons
        btn_row = QHBoxLayout()

        self._open_btn = QPushButton(lang.get("bookmark_open", "Open"))
        self._open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(self._open_btn)

        self._remove_btn = QPushButton(lang.get("bookmark_remove", "Remove"))
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._remove_btn)

        self._clear_btn = QPushButton(lang.get("bookmark_clear", "Clear All"))
        self._clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(self._clear_btn)

        close_btn = QPushButton(lang.get("bookmark_close", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        self._refresh()

    def _refresh(self):
        self._list.clear()
        bookmarks = get_bookmarks()
        lang = language_wrapper.language_word_dict
        self._count_label.setText(
            lang.get("bookmark_count", "{count} bookmarked image(s)").format(count=len(bookmarks))
        )
        for path in bookmarks:
            item = QListWidgetItem(path)
            if not Path(path).exists():
                item.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(item)

    def _on_double_click(self, item: QListWidgetItem):
        path = item.text()
        if Path(path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            self.main_gui.clear_tile_grid()
            open_path(main_gui=self.main_gui, path=path)
            self.close()

    def _open_selected(self):
        items = self._list.selectedItems()
        if not items:
            return
        path = items[0].text()
        if Path(path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            self.main_gui.clear_tile_grid()
            open_path(main_gui=self.main_gui, path=path)
            self.close()

    def _remove_selected(self):
        items = self._list.selectedItems()
        for item in items:
            remove_bookmark(item.text())
        self._refresh()

    def _clear_all(self):
        lang = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self,
            lang.get("bookmark_clear_confirm_title", "Clear Bookmarks"),
            lang.get("bookmark_clear_confirm", "Remove all bookmarks?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_bookmarks()
            self._refresh()
