"""Tag & Album manager dialog — manage custom tags and virtual albums."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QInputDialog, QTabWidget, QWidget,
    QMenu,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.tags import (
    get_all_tags, get_tags_for_image, add_tag, remove_tag,
    create_tag, delete_tag, rename_tag,
    get_all_albums, create_album, delete_album, rename_album,
    add_to_album, remove_from_album, get_album_images,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


# Translation keys and fallbacks — centralised so each literal appears once.
_K_TAG_CREATE = "tag_create"
_K_TAG_CREATE_PROMPT = "tag_create_prompt"
_K_ALBUM_CREATE = "album_create"
_K_ALBUM_CREATE_PROMPT = "album_create_prompt"
_K_RENAME_FALLBACK = "Rename"
_K_TAG_CREATE_FALLBACK = "New Tag"
_K_ALBUM_CREATE_FALLBACK = "New Album"
_K_TAG_NAME_FALLBACK = "Tag name:"
_K_ALBUM_NAME_FALLBACK = "Album name:"


def open_tag_album_dialog(main_gui: GPUImageView):
    dlg = TagAlbumDialog(main_gui)
    dlg.exec()


class TagAlbumDialog(QDialog):
    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self.main_gui = main_gui
        self._lang = language_wrapper.language_word_dict

        self.setWindowTitle(self._lang.get("tag_album_title", "Tags & Albums"))
        self.setMinimumSize(600, 480)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Tab 1: Tags
        self._tag_widget = self._build_tag_tab()
        self._tabs.addTab(self._tag_widget, self._lang.get("tag_tab_tags", "Tags"))

        # Tab 2: Albums
        self._album_widget = self._build_album_tab()
        self._tabs.addTab(self._album_widget, self._lang.get("tag_tab_albums", "Albums"))

        # Close
        close_btn = QPushButton(self._lang.get("tag_close", "Close"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    # ===========================
    # Tags Tab
    # ===========================
    def _build_tag_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Tag list (left) + images (right)
        row = QHBoxLayout()

        # Left: tag list
        left = QVBoxLayout()
        self._tag_count = QLabel()
        left.addWidget(self._tag_count)

        self._tag_list = QListWidget()
        self._tag_list.currentItemChanged.connect(self._on_tag_selected)
        left.addWidget(self._tag_list)

        tag_btn_row = QHBoxLayout()
        add_btn = QPushButton(self._lang.get(_K_TAG_CREATE, _K_TAG_CREATE_FALLBACK))
        add_btn.clicked.connect(self._create_tag)
        tag_btn_row.addWidget(add_btn)

        rename_btn = QPushButton(self._lang.get("tag_rename", _K_RENAME_FALLBACK))
        rename_btn.clicked.connect(self._rename_tag)
        tag_btn_row.addWidget(rename_btn)

        del_btn = QPushButton(self._lang.get("tag_delete", "Delete"))
        del_btn.clicked.connect(self._delete_tag)
        tag_btn_row.addWidget(del_btn)

        left.addLayout(tag_btn_row)
        row.addLayout(left, 1)

        # Right: images in selected tag
        right = QVBoxLayout()
        self._tag_image_label = QLabel(self._lang.get("tag_images", "Images in tag:"))
        right.addWidget(self._tag_image_label)

        self._tag_image_list = QListWidget()
        self._tag_image_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._tag_image_list.itemDoubleClicked.connect(self._open_tag_image)
        right.addWidget(self._tag_image_list)

        img_btn_row = QHBoxLayout()
        remove_img_btn = QPushButton(self._lang.get("tag_remove_image", "Remove from Tag"))
        remove_img_btn.clicked.connect(self._remove_image_from_tag)
        img_btn_row.addWidget(remove_img_btn)

        filter_btn = QPushButton(self._lang.get("tag_filter", "Show in Viewer"))
        filter_btn.clicked.connect(self._filter_by_tag)
        img_btn_row.addWidget(filter_btn)

        right.addLayout(img_btn_row)
        row.addLayout(right, 2)

        layout.addLayout(row)
        self._refresh_tags()
        return w

    def _refresh_tags(self):
        self._tag_list.clear()
        self._tag_image_list.clear()
        tags = get_all_tags()
        self._tag_count.setText(
            self._lang.get("tag_count", "{count} tag(s)").format(count=len(tags))
        )
        for name, paths in sorted(tags.items()):
            item = QListWidgetItem(f"{name}  ({len(paths)})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._tag_list.addItem(item)

    def _on_tag_selected(self, current, _prev):
        self._tag_image_list.clear()
        if not current:
            return
        tag_name = current.data(Qt.ItemDataRole.UserRole)
        tags = get_all_tags()
        for path in tags.get(tag_name, []):
            item = QListWidgetItem(path)
            if not Path(path).exists():
                item.setForeground(Qt.GlobalColor.gray)
            self._tag_image_list.addItem(item)

    def _create_tag(self):
        name, ok = QInputDialog.getText(
            self, self._lang.get(_K_TAG_CREATE, _K_TAG_CREATE_FALLBACK),
            self._lang.get(_K_TAG_CREATE_PROMPT, _K_TAG_NAME_FALLBACK))
        if ok and name.strip():
            create_tag(name.strip())
            self._refresh_tags()

    def _rename_tag(self):
        item = self._tag_list.currentItem()
        if not item:
            return
        old = item.data(Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(
            self, self._lang.get("tag_rename", _K_RENAME_FALLBACK),
            self._lang.get("tag_rename_prompt", "New name:"), text=old)
        if ok and new_name.strip() and new_name.strip() != old:
            rename_tag(old, new_name.strip())
            self._refresh_tags()

    def _delete_tag(self):
        item = self._tag_list.currentItem()
        if not item:
            return
        tag_name = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            self._lang.get("tag_delete_confirm_title", "Delete Tag"),
            self._lang.get("tag_delete_confirm", "Delete tag '{name}'?").format(name=tag_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_tag(tag_name)
            self._refresh_tags()

    def _remove_image_from_tag(self):
        tag_item = self._tag_list.currentItem()
        if not tag_item:
            return
        tag_name = tag_item.data(Qt.ItemDataRole.UserRole)
        for item in self._tag_image_list.selectedItems():
            remove_tag(tag_name, item.text())
        self._refresh_tags()
        # Re-select same tag
        for i in range(self._tag_list.count()):
            if self._tag_list.item(i).data(Qt.ItemDataRole.UserRole) == tag_name:
                self._tag_list.setCurrentRow(i)
                break

    def _open_tag_image(self, item: QListWidgetItem):
        path = item.text()
        if Path(path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            self.main_gui.clear_tile_grid()
            open_path(main_gui=self.main_gui, path=path)
            self.close()

    def _filter_by_tag(self):
        tag_item = self._tag_list.currentItem()
        if not tag_item:
            return
        tag_name = tag_item.data(Qt.ItemDataRole.UserRole)
        tags = get_all_tags()
        images = [p for p in tags.get(tag_name, []) if Path(p).is_file()]
        if not images:
            return
        viewer = self.main_gui
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(images)
        self.close()

    # ===========================
    # Albums Tab
    # ===========================
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
        add_btn = QPushButton(self._lang.get(_K_ALBUM_CREATE, _K_ALBUM_CREATE_FALLBACK))
        add_btn.clicked.connect(self._create_album)
        album_btn_row.addWidget(add_btn)

        rename_btn = QPushButton(self._lang.get("album_rename", _K_RENAME_FALLBACK))
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
        for name, paths in sorted(albums.items()):
            item = QListWidgetItem(f"{name}  ({len(paths)})")
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
        name, ok = QInputDialog.getText(
            self, self._lang.get(_K_ALBUM_CREATE, _K_ALBUM_CREATE_FALLBACK),
            self._lang.get(_K_ALBUM_CREATE_PROMPT, _K_ALBUM_NAME_FALLBACK))
        if ok and name.strip():
            create_album(name.strip())
            self._refresh_albums()

    def _rename_album(self):
        item = self._album_list.currentItem()
        if not item:
            return
        old = item.data(Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(
            self, self._lang.get("album_rename", _K_RENAME_FALLBACK),
            self._lang.get("album_rename_prompt", "New name:"), text=old)
        if ok and new_name.strip() and new_name.strip() != old:
            rename_album(old, new_name.strip())
            self._refresh_albums()

    def _delete_album(self):
        item = self._album_list.currentItem()
        if not item:
            return
        album_name = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            self._lang.get("album_delete_confirm_title", "Delete Album"),
            self._lang.get("album_delete_confirm", "Delete album '{name}'?")
                .format(name=album_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
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
        path = item.text()
        if Path(path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            self.main_gui.clear_tile_grid()
            open_path(main_gui=self.main_gui, path=path)
            self.close()

    def _view_album(self):
        album_item = self._album_list.currentItem()
        if not album_item:
            return
        album_name = album_item.data(Qt.ItemDataRole.UserRole)
        images = [p for p in get_album_images(album_name) if Path(p).is_file()]
        if not images:
            return
        viewer = self.main_gui
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(images)
        self.close()


# ===========================
# Quick tag/album context menu helpers
# ===========================

def build_tag_submenu(main_gui: GPUImageView, path: str, parent_menu: QMenu):
    """Build 'Add to Tag' submenu for right-click context menu."""
    lang = language_wrapper.language_word_dict
    tag_menu = parent_menu.addMenu(lang.get("tag_menu_title", "Tags"))

    tags = get_all_tags()
    current_tags = get_tags_for_image(path)

    for tag_name in sorted(tags.keys()):
        action = tag_menu.addAction(tag_name)
        action.setCheckable(True)
        action.setChecked(tag_name in current_tags)
        action.triggered.connect(
            lambda checked, t=tag_name: _toggle_tag(main_gui, t, path)
        )

    if tags:
        tag_menu.addSeparator()

    new_action = tag_menu.addAction(lang.get("tag_create_and_add", "+ New Tag..."))
    new_action.triggered.connect(lambda: _create_and_add_tag(main_gui, path))


def build_album_submenu(main_gui: GPUImageView, path: str, parent_menu: QMenu):
    """Build 'Add to Album' submenu for right-click context menu."""
    lang = language_wrapper.language_word_dict
    album_menu = parent_menu.addMenu(lang.get("album_menu_title", "Albums"))

    albums = get_all_albums()

    for album_name in sorted(albums.keys()):
        in_album = path in albums[album_name]
        action = album_menu.addAction(album_name)
        action.setCheckable(True)
        action.setChecked(in_album)
        action.triggered.connect(
            lambda checked, a=album_name: _toggle_album(main_gui, a, path)
        )

    if albums:
        album_menu.addSeparator()

    new_action = album_menu.addAction(lang.get("album_create_and_add", "+ New Album..."))
    new_action.triggered.connect(lambda: _create_and_add_album(main_gui, path))


def build_batch_tag_album_submenu(main_gui: GPUImageView, paths: list[str], parent_menu: QMenu):
    """Build tag/album submenu for batch selected images."""
    lang = language_wrapper.language_word_dict

    # Batch add to tag
    tag_menu = parent_menu.addMenu(lang.get("batch_tag_title", "Add to Tag"))
    tags = get_all_tags()
    for tag_name in sorted(tags.keys()):
        action = tag_menu.addAction(tag_name)
        action.triggered.connect(
            lambda checked, t=tag_name: _batch_add_tag(main_gui, t, paths)
        )
    if tags:
        tag_menu.addSeparator()
    new_action = tag_menu.addAction(lang.get("tag_create_and_add", "+ New Tag..."))
    new_action.triggered.connect(lambda: _batch_create_and_add_tag(main_gui, paths))

    # Batch add to album
    album_menu = parent_menu.addMenu(lang.get("batch_album_title", "Add to Album"))
    albums = get_all_albums()
    for album_name in sorted(albums.keys()):
        action = album_menu.addAction(album_name)
        action.triggered.connect(
            lambda checked, a=album_name: _batch_add_album(main_gui, a, paths)
        )
    if albums:
        album_menu.addSeparator()
    new_action = album_menu.addAction(lang.get("album_create_and_add", "+ New Album..."))
    new_action.triggered.connect(lambda: _batch_create_and_add_album(main_gui, paths))


def _toggle_tag(main_gui: GPUImageView, tag_name: str, path: str):
    if path in get_all_tags().get(tag_name, []):
        remove_tag(tag_name, path)
        _toast(main_gui, f"Removed from '{tag_name}'")
    else:
        add_tag(tag_name, path)
        _toast(main_gui, f"Tagged '{tag_name}'")


def _create_and_add_tag(main_gui: GPUImageView, path: str):
    lang = language_wrapper.language_word_dict
    name, ok = QInputDialog.getText(
        main_gui, lang.get(_K_TAG_CREATE, _K_TAG_CREATE_FALLBACK),
        lang.get(_K_TAG_CREATE_PROMPT, _K_TAG_NAME_FALLBACK))
    if ok and name.strip():
        create_tag(name.strip())
        add_tag(name.strip(), path)
        _toast(main_gui, f"Tagged '{name.strip()}'")


def _toggle_album(main_gui: GPUImageView, album_name: str, path: str):
    if path in get_all_albums().get(album_name, []):
        remove_from_album(album_name, path)
        _toast(main_gui, f"Removed from '{album_name}'")
    else:
        add_to_album(album_name, path)
        _toast(main_gui, f"Added to '{album_name}'")


def _create_and_add_album(main_gui: GPUImageView, path: str):
    lang = language_wrapper.language_word_dict
    name, ok = QInputDialog.getText(
        main_gui, lang.get(_K_ALBUM_CREATE, _K_ALBUM_CREATE_FALLBACK),
        lang.get(_K_ALBUM_CREATE_PROMPT, _K_ALBUM_NAME_FALLBACK))
    if ok and name.strip():
        create_album(name.strip())
        add_to_album(name.strip(), path)
        _toast(main_gui, f"Added to '{name.strip()}'")


def _batch_add_tag(main_gui: GPUImageView, tag_name: str, paths: list[str]):
    count = sum(1 for p in paths if add_tag(tag_name, p))
    _toast(main_gui, f"Tagged {count} image(s) as '{tag_name}'")


def _batch_create_and_add_tag(main_gui: GPUImageView, paths: list[str]):
    lang = language_wrapper.language_word_dict
    name, ok = QInputDialog.getText(
        main_gui, lang.get(_K_TAG_CREATE, _K_TAG_CREATE_FALLBACK),
        lang.get(_K_TAG_CREATE_PROMPT, _K_TAG_NAME_FALLBACK))
    if ok and name.strip():
        create_tag(name.strip())
        count = sum(1 for p in paths if add_tag(name.strip(), p))
        _toast(main_gui, f"Tagged {count} image(s) as '{name.strip()}'")


def _batch_add_album(main_gui: GPUImageView, album_name: str, paths: list[str]):
    count = sum(1 for p in paths if add_to_album(album_name, p))
    _toast(main_gui, f"Added {count} image(s) to '{album_name}'")


def _batch_create_and_add_album(main_gui: GPUImageView, paths: list[str]):
    lang = language_wrapper.language_word_dict
    name, ok = QInputDialog.getText(
        main_gui, lang.get(_K_ALBUM_CREATE, _K_ALBUM_CREATE_FALLBACK),
        lang.get(_K_ALBUM_CREATE_PROMPT, _K_ALBUM_NAME_FALLBACK))
    if ok and name.strip():
        create_album(name.strip())
        count = sum(1 for p in paths if add_to_album(name.strip(), p))
        _toast(main_gui, f"Added {count} image(s) to '{name.strip()}'")


def _toast(main_gui: GPUImageView, msg: str):
    if hasattr(main_gui.main_window, "toast"):
        main_gui.main_window.toast.info(msg)
