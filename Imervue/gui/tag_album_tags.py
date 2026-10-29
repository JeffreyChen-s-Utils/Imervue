"""Tags tab of :class:`~Imervue.gui.tag_album_dialog.TagAlbumDialog`.

``TagTabMixin`` builds the tag list and the images-in-tag list, and owns
create / rename / delete of a tag, removing images from it, opening one image
and showing the tag's files in the viewer. It relies on the host dialog's
``_lang``, ``main_gui``, ``_usable_name`` and ``close``.
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
    RENAME_FALLBACK, TAG_CREATE, TAG_CREATE_FALLBACK, TAG_CREATE_PROMPT, TAG_NAME_FALLBACK,
    collection_rows, entered_name, viewable_images,
)
from Imervue.user_settings.tags import (
    create_tag, delete_tag, get_all_tags, remove_tag, rename_tag,
)


class TagTabMixin:
    """The Tags tab of the Tags & Albums dialog."""

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
        add_btn = QPushButton(self._lang.get(TAG_CREATE, TAG_CREATE_FALLBACK))
        add_btn.clicked.connect(self._create_tag)
        tag_btn_row.addWidget(add_btn)

        rename_btn = QPushButton(self._lang.get("tag_rename", RENAME_FALLBACK))
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
        for label, name in collection_rows(tags):
            item = QListWidgetItem(label)
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
        name = entered_name(*QInputDialog.getText(
            self, self._lang.get(TAG_CREATE, TAG_CREATE_FALLBACK),
            self._lang.get(TAG_CREATE_PROMPT, TAG_NAME_FALLBACK)))
        if name and self._usable_name(name, get_all_tags()):
            create_tag(name)
            self._refresh_tags()

    def _rename_tag(self):
        item = self._tag_list.currentItem()
        if not item:
            return
        old = item.data(Qt.ItemDataRole.UserRole)
        new_name = entered_name(*QInputDialog.getText(
            self, self._lang.get("tag_rename", RENAME_FALLBACK),
            self._lang.get("tag_rename_prompt", "New name:"), text=old))
        if new_name and new_name != old and self._usable_name(new_name, get_all_tags(), old):
            rename_tag(old, new_name)
            self._refresh_tags()

    def _delete_tag(self):
        item = self._tag_list.currentItem()
        if not item:
            return
        tag_name = item.data(Qt.ItemDataRole.UserRole)
        question = self._lang.get(
            "tag_delete_confirm", "Delete tag '{name}'?").format(name=tag_name)
        if confirm(self, self._lang.get("tag_delete_confirm_title", "Delete Tag"), question):
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
        images = viewable_images(tags.get(tag_name, []))
        if not images:
            return
        viewer = self.main_gui
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(images)
        self.close()
