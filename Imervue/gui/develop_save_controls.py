"""Explicit save destinations for the Modify workspace."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy

from Imervue.image.in_place_save import can_rewrite_in_place
from Imervue.multi_language.language_wrapper import language_wrapper


def is_source_destination(target: str, source: str) -> bool:
    """Recognize the source path, including existing hard links and symlinks."""
    if Path(target).resolve() == Path(source).resolve():
        return True
    if os.path.exists(target) and os.path.exists(source):
        return os.path.samefile(target, source)
    return False


def _path_label() -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                 | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label


class DevelopSaveControlsMixin:
    """Save controls derive their policy from the bound source file."""

    def _build_save_controls(self, layout, lang: dict) -> None:
        self._save_destination = _path_label()
        layout.addWidget(self._save_destination)
        self._btn_ann_save = QPushButton(lang.get("modify_overwrite", "Overwrite original"))
        self._btn_ann_save.setProperty("primary", True)
        self._btn_ann_save.clicked.connect(self._save_annotation)
        self._btn_save_copy = QPushButton(lang.get("modify_save_copy", "Save copy…"))
        self._btn_save_copy.clicked.connect(self._save_copy)
        for button in (self._btn_ann_save, self._btn_save_copy):
            layout.addWidget(button)
            self._interactive_widgets.append(button)
        self._save_result = _path_label()
        self._save_result.hide()
        layout.addWidget(self._save_result)
        self._sync_save_controls()

    def _sync_save_controls(self) -> None:
        if not hasattr(self, "_save_destination"):
            return
        lang = language_wrapper.language_word_dict
        path = self._path
        writable = bool(path and can_rewrite_in_place(path))
        self._btn_ann_save.setEnabled(writable)
        self._btn_save_copy.setEnabled(bool(path))
        self._crop_apply_btn.setEnabled(writable)
        self._save_result.clear()
        self._save_result.hide()
        label = lang.get("modify_source", "Original: {path}").format(path=path) if path else ""
        if path and not writable:
            label += "\n" + lang.get("modify_copy_required",
                "This format requires a copy. The original stays unchanged.")
        self._save_destination.setText(label)
        self._save_destination.setToolTip(path or "")
        consequence = (lang.get("modify_crop_overwrites",
            "Applying the crop overwrites the original file.") if writable else
            lang.get("modify_crop_copy_hint",
                "This format cannot be cropped in place. Save a copy first."))
        self._crop_consequence.setText(consequence)

    def _save_copy(self) -> None:
        if self._canvas is None or not self._canvas_source_path or not self._ensure_full_canvas():
            return
        from Imervue.gui.annotation_models import bake
        image = bake(self._canvas.get_base_pil(), self._canvas.get_annotations())
        self._save_annotation_copy(self._canvas_source_path, image)

    def _show_save_result(self, path: str) -> None:
        message = language_wrapper.language_word_dict.get(
            "modify_saved_to", "Saved to {path}").format(path=path)
        self._save_result.setText(message)
        self._save_result.show()
        self._toast(message, "success")

    def _show_save_failure(self, path: str) -> None:
        message = language_wrapper.language_word_dict.get("annotation_save_failed", "Save failed")
        self._save_result.setText(f"{message}\n{path}")
        self._save_result.show()
        self._toast(message, "warning")
