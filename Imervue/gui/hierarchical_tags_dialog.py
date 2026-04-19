"""
Hierarchical tags dialog — manage tree-structured tags (``animal/cat/british``).

Backed by ``library.image_index`` tag_nodes / image_tags tables; a parallel
system to the flat settings-based tags so users who already have flat tags
keep those working.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QListWidget, QMessageBox,
)

from Imervue.library import image_index
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class HierarchicalTagsDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("htags_title", "Hierarchical Tags"))
        self.resize(720, 520)

        layout = QHBoxLayout(self)

        # Left — tag tree + add/remove
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(lang.get("htags_tree", "Tag tree")))
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemSelectionChanged.connect(self._refresh_images)
        left_col.addWidget(self._tree, stretch=1)

        add_row = QHBoxLayout()
        self._new_tag_edit = QLineEdit()
        self._new_tag_edit.setPlaceholderText(
            lang.get("htags_new_placeholder", "animal/cat/british")
        )
        add_btn = QPushButton(lang.get("htags_add", "Create"))
        add_btn.clicked.connect(self._create_tag)
        del_btn = QPushButton(lang.get("htags_delete", "Delete"))
        del_btn.clicked.connect(self._delete_tag)
        add_row.addWidget(self._new_tag_edit, stretch=1)
        add_row.addWidget(add_btn)
        add_row.addWidget(del_btn)
        left_col.addLayout(add_row)

        # Right — images under selected tag
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel(lang.get("htags_images", "Images under tag")))
        self._images_list = QListWidget()
        right_col.addWidget(self._images_list, stretch=1)

        assign_row = QHBoxLayout()
        assign_btn = QPushButton(lang.get("htags_assign_selected", "Tag selected tiles"))
        assign_btn.clicked.connect(self._assign_selected)
        remove_btn = QPushButton(lang.get("htags_remove_from_tag", "Untag selected tiles"))
        remove_btn.clicked.connect(self._remove_from_selected)
        assign_row.addWidget(assign_btn)
        assign_row.addWidget(remove_btn)
        right_col.addLayout(assign_row)

        layout.addLayout(left_col, stretch=1)
        layout.addLayout(right_col, stretch=1)

        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        right_col.addWidget(close_btn)

        self._refresh_tree()

    # ---------- Data ----------

    def _refresh_tree(self) -> None:
        self._tree.clear()
        paths = image_index.all_tag_paths()
        nodes: dict[str, QTreeWidgetItem] = {}
        for p in paths:
            parts = p.split("/")
            parent_item: QTreeWidgetItem | None = None
            for i, part in enumerate(parts):
                key = "/".join(parts[: i + 1])
                if key in nodes:
                    parent_item = nodes[key]
                    continue
                item = QTreeWidgetItem([part])
                item.setData(0, Qt.ItemDataRole.UserRole, key)
                if parent_item is None:
                    self._tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                nodes[key] = item
                parent_item = item
        self._tree.expandAll()

    def _selected_tag_path(self) -> str | None:
        items = self._tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    def _refresh_images(self) -> None:
        tag = self._selected_tag_path()
        self._images_list.clear()
        if not tag:
            return
        for p in image_index.images_with_tag(tag):
            self._images_list.addItem(p)

    # ---------- Actions ----------

    def _create_tag(self) -> None:
        text = self._new_tag_edit.text().strip()
        if not text:
            return
        try:
            image_index.create_tag_path(text)
        except ValueError:
            QMessageBox.warning(self, "", "Invalid tag path")
            return
        self._new_tag_edit.clear()
        self._refresh_tree()

    def _delete_tag(self) -> None:
        tag = self._selected_tag_path()
        if not tag:
            return
        if QMessageBox.question(
            self, "",
            f"Delete '{tag}' and all descendants?",
        ) != QMessageBox.StandardButton.Yes:
            return
        image_index.delete_tag_path(tag)
        self._refresh_tree()
        self._images_list.clear()

    def _assign_selected(self) -> None:
        tag = self._selected_tag_path()
        if not tag:
            return
        viewer = self._ui.viewer
        paths = list(viewer.selected_tiles) or (
            [viewer.model.images[viewer.current_index]]
            if viewer.deep_zoom and viewer.model.images else []
        )
        if not paths:
            return
        for p in paths:
            image_index.add_image_tag(p, tag)
        self._refresh_images()
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(f"Tagged {len(paths)} image(s) as {tag}")

    def _remove_from_selected(self) -> None:
        tag = self._selected_tag_path()
        if not tag:
            return
        viewer = self._ui.viewer
        paths = list(viewer.selected_tiles)
        removed = 0
        for p in paths:
            if image_index.remove_image_tag(p, tag):
                removed += 1
        self._refresh_images()
        if hasattr(self._ui, "toast"):
            self._ui.toast.info(f"Untagged {removed} image(s) from {tag}")


def open_hierarchical_tags(ui: ImervueMainWindow) -> None:
    HierarchicalTagsDialog(ui).exec()
