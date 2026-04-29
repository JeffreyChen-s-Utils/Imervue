"""Smart Crop plugin — saliency-driven crop-rect suggestions.

Pure-numpy heuristic; no ML model, no extra dependencies. Suggests one
crop frame per aspect ratio (free / 1:1 / 4:5 / 3:2 / 16:9) with the
centre of saliency mass landing on a rule-of-thirds anchor. Chosen
crop is written into ``recipe.extra['layers']`` as a virtual rectangle
the user can apply via Develop > Crop.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

from Imervue.image.saliency import CropSuggestion, suggest_crops

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.smart_crop")


class SmartCropPlugin(ImervuePlugin):
    plugin_name = "Smart Crop"
    plugin_version = "1.0.0"
    plugin_description = "Saliency + rule-of-thirds crop suggestions."
    plugin_author = "Imervue"

    def on_build_menu_bar(self, menu_bar) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        # Reuse the Extra Tools menu so the action sits with other crop tools.
        for action in menu_bar.actions():
            if action.menu() and action.text().strip() == lang.get(
                "extra_tools_menu", "Extra Tools",
            ):
                # Find the "Retouch & Transform" submenu and add to it.
                for sub_action in action.menu().actions():
                    if sub_action.menu() and sub_action.text().strip() == lang.get(
                        "retouch_submenu", "Retouch & Transform",
                    ):
                        entry = sub_action.menu().addAction(
                            lang.get("smart_crop_title", "Smart Crop")
                        )
                        entry.triggered.connect(self._open_dialog)
                        return

    def _open_dialog(self) -> None:
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return
        images = getattr(viewer.model, "images", [])
        idx = getattr(viewer, "current_index", -1)
        if not (0 <= idx < len(images)):
            return
        path = images[idx]
        try:
            arr = _load_rgba(path)
        except (OSError, ValueError):
            logger.exception("Smart crop failed to load %s", path)
            return
        suggestions = suggest_crops(arr)
        SmartCropDialog(viewer, path, suggestions).exec()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


class SmartCropDialog(QDialog):
    """Picks one of the suggested crops and writes it into the recipe."""

    def __init__(
        self,
        viewer: GPUImageView,
        path: str,
        suggestions: dict[str, CropSuggestion],
        parent=None,
    ):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._suggestions = suggestions
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("smart_crop_title", "Smart Crop"))
        self.setMinimumWidth(440)

        self._list = QListWidget()
        for preset_id, suggestion in suggestions.items():
            label = lang.get(f"smart_crop_preset_{preset_id}", preset_id)
            item = QListWidgetItem(
                f"{label}  —  {suggestion.w}×{suggestion.h}  "
                f"(score {suggestion.score:.0f})"
            )
            item.setData(Qt.ItemDataRole.UserRole, preset_id)
            self._list.addItem(item)
        self._list.setCurrentRow(0)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get(
                "smart_crop_intro",
                "Pick a crop suggestion to write into the image's recipe.",
            )
        ))
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(self._build_button_box())

    def _build_button_box(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        return buttons

    def _commit(self) -> None:
        item = self._list.currentItem()
        if item is None:
            self.reject()
            return
        preset_id = item.data(Qt.ItemDataRole.UserRole)
        suggestion = self._suggestions.get(preset_id)
        if suggestion is None:
            self.reject()
            return
        recipe = recipe_store.get_for_path(self._path) or Recipe()
        recipe.crop = (suggestion.x, suggestion.y, suggestion.w, suggestion.h)
        recipe_store.set_for_path(self._path, recipe)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()
