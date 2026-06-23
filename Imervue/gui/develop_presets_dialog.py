"""Develop-preset browser: save the current recipe as a named preset and apply
presets to the current image or a tile selection (batch sync).

The CRUD and apply logic live in :mod:`Imervue.image.develop_presets`; this
dialog is the thin Qt front-end over them.
"""
from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.develop_presets import (
    DevelopPresetStore,
    apply_recipe_to_paths,
    merge_recipe_into_paths,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict

logger = logging.getLogger("Imervue.gui.develop_presets_dialog")

_DIALOG_TITLE = "Develop Presets"


class DevelopPresetsDialog(QDialog):
    """Save / apply / rename / delete named develop presets."""

    def __init__(self, viewer, parent=None) -> None:
        super().__init__(parent)
        self._viewer = viewer
        self._store = DevelopPresetStore(user_setting_dict)
        self.setWindowTitle(_DIALOG_TITLE)
        self.resize(360, 420)
        self._list = QListWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addLayout(self._build_buttons())
        self._refresh()

    def _build_buttons(self) -> QVBoxLayout:
        outer = QVBoxLayout()
        manage = QHBoxLayout()
        self._add_button(manage, "Save Current As…", self._save_current_as)
        self._add_button(manage, "Rename", self._rename)
        self._add_button(manage, "Delete", self._delete)
        apply_row = QHBoxLayout()
        self._add_button(apply_row, "Apply to Current", self._apply_current)
        self._add_button(apply_row, "Apply to Selection", self._apply_selection)
        self._add_button(apply_row, "Merge Adjustments", self._merge_selection)
        outer.addLayout(manage)
        outer.addLayout(apply_row)
        return outer

    def _add_button(self, row: QHBoxLayout, text: str, slot) -> None:
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        row.addWidget(button)

    def _refresh(self) -> None:
        self._list.clear()
        self._list.addItems(self._store.names())

    # -- helpers ------------------------------------------------------

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        return item.text() if item is not None else None

    def _current_path(self) -> str | None:
        images = getattr(self._viewer.model, "images", [])
        idx = getattr(self._viewer, "current_index", -1)
        return str(images[idx]) if 0 <= idx < len(images) else None

    def _target_paths(self) -> list[str]:
        selected = getattr(self._viewer, "selected_tiles", None)
        if selected:
            return [str(p) for p in selected]
        path = self._current_path()
        return [path] if path else []

    def _reload_current(self) -> None:
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook()

    # -- actions ------------------------------------------------------

    def _save_current_as(self) -> None:
        path = self._current_path()
        if path is None:
            return
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        recipe = recipe_store.get_for_path(path) or Recipe()
        self._store.save(name, recipe)
        schedule_save()
        self._refresh()

    def _rename(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        new, ok = QInputDialog.getText(self, "Rename Preset", "New name:", text=name)
        if ok and self._store.rename(name, new):
            schedule_save()
            self._refresh()

    def _delete(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        confirm = QMessageBox.question(self, "Delete Preset", f"Delete '{name}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            self._store.delete(name)
            schedule_save()
            self._refresh()

    def _apply_current(self) -> None:
        path = self._current_path()
        recipe = self._selected_recipe()
        if path is None or recipe is None:
            return
        apply_recipe_to_paths(recipe, [path], recipe_store)
        self._reload_current()

    def _apply_selection(self) -> None:
        recipe = self._selected_recipe()
        if recipe is None:
            return
        count = apply_recipe_to_paths(recipe, self._target_paths(), recipe_store)
        self._reload_current()
        QMessageBox.information(
            self, _DIALOG_TITLE, f"Applied to {count} image(s).")

    def _merge_selection(self) -> None:
        recipe = self._selected_recipe()
        if recipe is None:
            return
        count = merge_recipe_into_paths(recipe, self._target_paths(), recipe_store)
        self._reload_current()
        QMessageBox.information(
            self, _DIALOG_TITLE, f"Merged adjustments into {count} image(s).")

    def _selected_recipe(self) -> Recipe | None:
        name = self._selected_name()
        return self._store.get(name) if name is not None else None


def open_develop_presets_dialog(viewer) -> None:
    """Open the develop-preset browser for *viewer*."""
    parent = getattr(viewer, "main_window", viewer)
    DevelopPresetsDialog(viewer, parent).exec()
