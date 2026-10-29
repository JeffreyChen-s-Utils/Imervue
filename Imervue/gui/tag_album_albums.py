"""Albums tab of :class:`~Imervue.gui.tag_album_dialog.TagAlbumDialog`.

``AlbumTabMixin`` builds the album list and the images-in-album list, and owns
create / rename / delete of an album, removing images from it, opening one
image and viewing the album's files. It relies on the host dialog's ``_lang``,
``main_gui``, ``_usable_name``, ``_open_tag_image`` and ``close``.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
    QWidget,
)

from Imervue.gui.dialog_rows import confirm
from Imervue.gui.tag_album_logic import (
    ALBUM_CREATE, ALBUM_CREATE_FALLBACK, ALBUM_CREATE_PROMPT, ALBUM_NAME_FALLBACK,
    RENAME_FALLBACK, collection_rows, entered_name, viewable_images,
)
from Imervue.user_settings.tags import (
    create_album, delete_album, get_album_images, get_all_albums, remove_from_album, rename_album,
)


class AlbumTabMixin:
    """The Albums tab of the Tags & Albums dialog."""

    def _build_album_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        row = QHBoxLayout()

        # Left: album list
        left = QVBoxLayout()
        self._album_count = QLabel()
        left.addWidget(self._album_count)

        self._album_list = QListWidget()
        self._album_list.currentItemChanged.connect(self._on_album_selected)
        left.addWidget(self._album_list)

        album_btn_row = QHBoxLayout()
        add_btn = QPushButton(self._lang.get(ALBUM_CREATE, ALBUM_CREATE_FALLBACK))
        add_btn.clicked.connect(self._create_album)
        album_btn_row.addWidget(add_btn)

        rename_btn = QPushButton(self._lang.get("album_rename", RENAME_FALLBACK))
        rename_btn.clicked.connect(self._rename_album)
        album_btn_row.addWidget(rename_btn)

        del_btn = QPushButton(self._lang.get("album_delete", "Delete"))
        del_btn.clicked.connect(self._delete_album)
        album_btn_row.addWidget(del_btn)

        left.addLayout(album_btn_row)
        row.addLayout(left, 1)

        # Right: images in album
        right = QVBoxLayout()
        self._album_image_label = QLabel(self._lang.get("album_images", "Images in album:"))
        right.addWidget(self._album_image_label)

        self._album_image_list = QListWidget()
        self._album_image_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._album_image_list.itemDoubleClicked.connect(self._open_album_image)
        right.addWidget(self._album_image_list)

        img_btn_row = QHBoxLayout()
        remove_img_btn = QPushButton(self._lang.get("album_remove_image", "Remove from Album"))
        remove_img_btn.clicked.connect(self._remove_image_from_album)
        img_btn_row.addWidget(remove_img_btn)

        filter_btn = QPushButton(self._lang.get("album_view", "View Album"))
        filter_btn.clicked.connect(self._view_album)
        img_btn_row.addWidget(filter_btn)

        right.addLayout(img_btn_row)
        row.addLayout(right, 2)

        layout.addLayout(row)
        self._refresh_albums()
        return w

    def _refresh_albums(self):
        self._album_list.clear()
        self._album_image_list.clear()
        albums = get_all_albums()
        self._album_count.setText(
            self._lang.get("album_count", "{count} album(s)").format(count=len(albums))
        )
        for label, name in collection_rows(albums):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._album_list.addItem(item)

    def _on_album_selected(self, current, _prev):
        self._album_image_list.clear()
        if not current:
            return
        album_name = current.data(Qt.ItemDataRole.UserRole)
        for path in get_album_images(album_name):
            item = QListWidgetItem(path)
            if not Path(path).exists():
                item.setForeground(Qt.GlobalColor.gray)
            self._album_image_list.addItem(item)

    def _create_album(self):
        name = entered_name(*QInputDialog.getText(
            self, self._lang.get(ALBUM_CREATE, ALBUM_CREATE_FALLBACK),
            self._lang.get(ALBUM_CREATE_PROMPT, ALBUM_NAME_FALLBACK)))
        if name and self._usable_name(name, get_all_albums()):
            create_album(name)
            self._refresh_albums()

    def _rename_album(self):
        item = self._album_list.currentItem()
        if not item:
            return
        old = item.data(Qt.ItemDataRole.UserRole)
        new_name = entered_name(*QInputDialog.getText(
            self, self._lang.get("album_rename", RENAME_FALLBACK),
            self._lang.get("album_rename_prompt", "New name:"), text=old))
        if new_name and new_name != old and self._usable_name(new_name, get_all_albums(), old):
            rename_album(old, new_name)
            self._refresh_albums()

    def _delete_album(self):
        item = self._album_list.currentItem()
        if not item:
            return
        album_name = item.data(Qt.ItemDataRole.UserRole)
        if confirm(self, self._lang.get("album_delete_confirm_title", "Delete Album"),
                   self._lang.get("album_delete_confirm", "Delete album '{name}'?")
                   .format(name=album_name)):
            delete_album(album_name)
            self._refresh_albums()

    def _remove_image_from_album(self):
        album_item = self._album_list.currentItem()
        if not album_item:
            return
        album_name = album_item.data(Qt.ItemDataRole.UserRole)
        for item in self._album_image_list.selectedItems():
            remove_from_album(album_name, item.text())
        self._refresh_albums()
        for i in range(self._album_list.count()):
            if self._album_list.item(i).data(Qt.ItemDataRole.UserRole) == album_name:
                self._album_list.setCurrentRow(i)
                break

    def _open_album_image(self, item: QListWidgetItem):
        self._open_tag_image(item)

    def _view_album(self):
        album_item = self._album_list.currentItem()
        if not album_item:
            return
        album_name = album_item.data(Qt.ItemDataRole.UserRole)
        images = viewable_images(get_album_images(album_name))
        if not images:
            return
        viewer = self.main_gui
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(images)
        self.close()
