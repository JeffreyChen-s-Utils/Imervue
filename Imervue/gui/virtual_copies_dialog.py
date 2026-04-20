"""
Virtual Copies — named recipe variants per image.

Lets the user snapshot the current recipe under a name, and later
swap back to any saved variant. Variants are stored alongside the
master recipe in ``recipe_store`` and never touch the original pixels.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.virtual_copies_dialog")


class VirtualCopiesDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("vcopies_title", "Virtual Copies"))
        self.setMinimumWidth(360)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._snap_btn = QPushButton(lang.get("vcopies_snap", "Snap current →"))
        self._apply_btn = QPushButton(lang.get("vcopies_apply", "Apply"))
        self._rename_btn = QPushButton(lang.get("vcopies_rename", "Rename"))
        self._delete_btn = QPushButton(lang.get("vcopies_delete", "Delete"))

        self._snap_btn.clicked.connect(self._snap)
        self._apply_btn.clicked.connect(self._apply)
        self._rename_btn.clicked.connect(self._rename)
        self._delete_btn.clicked.connect(self._delete)

        side = QVBoxLayout()
        side.addWidget(self._snap_btn)
        side.addWidget(self._apply_btn)
        side.addWidget(self._rename_btn)
        side.addWidget(self._delete_btn)
        side.addStretch(1)

        body = QHBoxLayout()
        body.addWidget(self._list, 1)
        body.addLayout(side)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("vcopies_hint", "Named snapshots of this image's recipe — swap any time."),
        ))
        layout.addLayout(body, 1)
        layout.addWidget(buttons)

        self._reload()

    def _reload(self) -> None:
        self._list.clear()
        for name in recipe_store.list_variants_for_path(self._path):
            self._list.addItem(name)

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        return item.text() if item is not None else None

    def _snap(self) -> None:
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("vcopies_snap_title", "Snapshot name"),
            lang.get("vcopies_snap_prompt", "Name:"),
        )
        name = name.strip() if ok else ""
        if not name:
            return
        existing = set(recipe_store.list_variants_for_path(self._path))
        if name in existing:
            QMessageBox.warning(
                self,
                lang.get("vcopies_snap_title", "Snapshot name"),
                lang.get("vcopies_exists", "A snapshot with that name already exists."),
            )
            return
        recipe = recipe_store.get_for_path(self._path) or Recipe()
        recipe_store.save_variant_for_path(self._path, name, recipe)
        self._reload()

    def _apply(self) -> None:
        name = self._selected_name()
        if not name:
            return
        recipe = recipe_store.get_variant_for_path(self._path, name)
        if recipe is None:
            return
        recipe_store.set_for_path(self._path, recipe)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)

    def _rename(self) -> None:
        lang = language_wrapper.language_word_dict
        name = self._selected_name()
        if not name:
            return
        new, ok = QInputDialog.getText(
            self,
            lang.get("vcopies_rename_title", "Rename snapshot"),
            lang.get("vcopies_new_name", "New name:"),
            text=name,
        )
        new = new.strip() if ok else ""
        if not new or new == name:
            return
        if not recipe_store.rename_variant_for_path(self._path, name, new):
            QMessageBox.warning(
                self,
                lang.get("vcopies_rename_title", "Rename snapshot"),
                lang.get("vcopies_rename_fail", "Rename failed — name may already exist."),
            )
            return
        self._reload()

    def _delete(self) -> None:
        name = self._selected_name()
        if not name:
            return
        recipe_store.delete_variant_for_path(self._path, name)
        self._reload()


def open_virtual_copies(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    VirtualCopiesDialog(viewer, str(path)).exec()
