"""
跳至第 N 張圖片對話框
Jump-to-index dialog — Ctrl+G in deep zoom / tile grid.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class GotoIndexDialog(QDialog):
    """Tiny modal for jumping to a 1-based image index."""

    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui

        lang = language_wrapper.language_word_dict
        total = len(main_gui.model.images)

        self.setWindowTitle(lang.get("goto_dialog_title", "Go to Image"))
        self.setModal(True)

        layout = QVBoxLayout(self)

        label = QLabel(
            lang.get(
                "goto_dialog_prompt",
                "Enter image number (1–{total}):",
            ).format(total=total)
        )
        layout.addWidget(label)

        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setValidator(QIntValidator(1, max(total, 1), self))
        # Prefill with current index for quick tweaks
        self._input.setText(str(min(main_gui.current_index + 1, max(total, 1))))
        self._input.selectAll()
        row.addWidget(self._input)

        self._total_label = QLabel(f"/ {total}")
        self._total_label.setStyleSheet("color: #888;")
        row.addWidget(self._total_label)
        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._input.setFocus()

    def _on_accept(self) -> None:
        text = self._input.text().strip()
        if not text.isdigit():
            self.reject()
            return
        idx = int(text) - 1
        gui = self._main_gui
        images = gui.model.images
        if not images:
            self.reject()
            return
        idx = max(0, min(idx, len(images) - 1))
        gui.current_index = idx

        if gui.tile_grid_mode:
            # Scroll grid to target and highlight — match paint_tile_grid math
            base_tile = gui.thumbnail_size or 256
            scaled_tile = base_tile * gui.tile_scale
            cell = scaled_tile + gui.tile_padding
            cols = max(1, int(gui.width() // cell))
            row_pos = idx // cols
            gui.grid_offset_y = -(row_pos * cell) + gui.height() / 3
            gui.selected_tiles = {images[idx]}
            gui.tile_selection_mode = True
            gui.update()
        else:
            gui.load_deep_zoom_image(images[idx])
        self.accept()


def open_goto_dialog(main_gui: GPUImageView) -> None:
    if not main_gui.model.images:
        return
    dlg = GotoIndexDialog(main_gui)
    dlg.exec()
