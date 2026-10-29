"""Choose original or developed pixels for a new Paint document."""
from __future__ import annotations

from enum import Enum
import logging

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from Imervue.gpu_image_view.images.image_loader import decode_image_file
from Imervue.gui.annotation_models import bake
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue.paint_handoff")


class PaintSource(Enum):
    """The pixels a handoff copies into a new document."""

    ORIGINAL = "original"
    CURRENT = "current"


class PaintHandoffDialog(QDialog):
    """Explicit source choice without changing existing Paint documents."""

    def __init__(self, path: str, *, has_annotations: bool, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_handoff_title", "Open in Paint"))
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        source = QLabel(path)
        source.setTextFormat(Qt.TextFormat.PlainText)
        source.setWordWrap(True)
        layout.addWidget(source)
        self.source = QComboBox()
        self.source.addItem(lang.get("paint_handoff_original", "Original image"),
                            PaintSource.ORIGINAL)
        self.source.addItem(lang.get("paint_handoff_current", "Current developed result"),
                            PaintSource.CURRENT)
        self.source.setAccessibleName(lang.get("paint_handoff_source", "Image content"))
        layout.addWidget(self.source)
        self.annotations = QCheckBox(lang.get("paint_handoff_annotations", "Include annotations"))
        self.annotations.setChecked(has_annotations)
        self.annotations.setEnabled(False)
        self.source.currentIndexChanged.connect(lambda _index: self.annotations.setEnabled(
            has_annotations and self.source.currentData() == PaintSource.CURRENT))
        layout.addWidget(self.annotations)
        notice = QLabel(lang.get("paint_handoff_notice",
            "Creates a new Paint document at full resolution. Existing documents stay open. "
            "The original option excludes adjustments and annotations."))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open
                                  | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Open).setText(
            lang.get("paint_handoff_title", "Open in Paint"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            lang.get("export_cancel", "Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.source.setFocus()

    def include_annotations(self) -> bool:
        """Only the developed result may include the Modify annotations."""
        return self.annotations.isEnabled() and self.annotations.isChecked()


def current_pixels(path: str, panel, *, include_annotations: bool) -> np.ndarray:
    """Read full-quality working pixels, or apply the stored recipe without a panel."""
    if panel is not None and panel._canvas_source_path == path and panel.canvas() is not None:
        if not panel._ensure_full_canvas():
            raise ValueError(language_wrapper.language_word_dict.get(
                "paint_handoff_render_failed", "Could not prepare the full-resolution result."))
        canvas = panel.canvas()
        image = canvas.get_base_pil()
        if include_annotations:
            image = bake(image, canvas.get_annotations())
        return np.array(image)
    recipe = recipe_store.get_for_path(path) or Recipe()
    return recipe.apply(decode_image_file(path, orient=recipe.base_is_oriented()))


def choose_paint_handoff(window) -> None:
    """Ask which content to copy, then open a new document after rendering succeeds."""
    images = window.viewer.model.images
    if not images or not 0 <= window.viewer.current_index < len(images):
        window.toast.info(language_wrapper.language_word_dict.get(
            "paint_handoff_no_image", "Open an image before sending it to Paint."))
        return
    path = images[window.viewer.current_index]
    panel = getattr(window, "modify_panel", None)
    has_annotations = available_annotations(path, panel)
    dialog = PaintHandoffDialog(path, has_annotations=has_annotations, parent=window)
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.source.currentData() == PaintSource.ORIGINAL:
            window._bind_paint_workspace_to_current_image(path=path)
            return
        open_current_result(window, path, panel, include_annotations=dialog.include_annotations())
    finally:
        dialog.deleteLater()


def available_annotations(path: str, panel) -> bool:
    """Settle pending geometry before promising that its overlays can be included."""
    if panel is None or panel._canvas_source_path != path or panel.canvas() is None:
        return False
    if not panel.canvas().get_annotations():
        return False
    if not panel._ensure_full_canvas():
        return False
    return bool(panel.canvas().get_annotations())


def open_current_result(window, path: str, panel, *, include_annotations: bool) -> None:
    """Copy rendered pixels into a fresh, unsaved Paint document."""
    try:
        pixels = current_pixels(path, panel, include_annotations=include_annotations)
    except (*IMAGE_READ_ERRORS, MemoryError) as exc:
        logger.exception("Could not render %s for Paint", path)
        window.toast.error(language_wrapper.language_word_dict.get(
            "annotation_load_failed", "Load failed: {error}").format(error=exc))
        return
    workspace = window.paint_workspace
    workspace.new_tab(width=1, height=1)
    workspace.load_image(pixels, source_path=path)
    workspace._set_tab_dirty(workspace.canvas(), True)
    window._main_tabs.setCurrentIndex(2)
