"""Soft proof dialog — pick an ICC profile and show the simulated preview."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.gui._apply_save import load_rgba
from Imervue.gui.file_filters import translated_filter
from Imervue.gui.dialog_rows import folder_picker_row, open_path_into
from Imervue.image.soft_proof import simulate_profile
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.soft_proof_dialog")

_PREVIEW_MAX = 640


class SoftProofDialog(QDialog):
    def __init__(self, viewer: GPUImageView, path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        # The full-size proof render, kept so a dialog resize can re-scale it to
        # fit the preview instead of leaving it clipped / undersized.
        self._proof_pixmap: QPixmap | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("proof_title", "Soft Proof"))
        self.setMinimumWidth(560)

        prof_row, self._profile_edit = folder_picker_row(
            lang.get("proof_profile", "ICC profile:"), self._pick_profile,
            browse_text=lang.get("export_browse", "Browse..."))

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(360)
        self._status = QLabel("")

        preview_btn = QPushButton(lang.get("proof_preview", "Preview"))
        preview_btn.clicked.connect(self._preview_profile)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(prof_row)
        layout.addWidget(preview_btn)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._status)
        layout.addWidget(buttons)

    def _pick_profile(self) -> None:
        lang = language_wrapper.language_word_dict
        open_path_into(
            self, self._profile_edit, lang.get("proof_profile", "ICC profile"),
            translated_filter("file_filter_icc_profiles", "ICC profiles", ("icc", "icm")))

    def _preview_profile(self) -> None:
        lang = language_wrapper.language_word_dict
        profile = self._profile_edit.text().strip()
        if not profile:
            self._status.setText(lang.get("proof_pick", "Select an ICC profile."))
            return
        try:
            img = Image.fromarray(load_rgba(self._path))
            img.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
            arr = np.asarray(img)
        except IMAGE_READ_ERRORS as err:
            self._status.setText(str(err))
            return
        result = simulate_profile(arr, profile)
        if result is None:
            self._status.setText(
                lang.get("proof_failed", "Profile load failed."))
            return
        simulated, mask = result
        # Overlay out-of-gamut pixels with magenta for visibility.
        overlay = simulated.copy()
        overlay[mask, 0] = 255
        overlay[mask, 1] = 0
        overlay[mask, 2] = 255
        qimg = QImage(overlay.data, overlay.shape[1], overlay.shape[0],
                      overlay.shape[1] * 4, QImage.Format.Format_RGBA8888).copy()
        self._proof_pixmap = QPixmap.fromImage(qimg)
        self._render_proof()
        oog = int(mask.sum())
        self._status.setText(
            lang.get("proof_oog", "Out-of-gamut pixels:") + f" {oog}",
        )

    def _render_proof(self) -> None:
        """Scale the proof render to the preview's current size (called after a
        proof and on resize, so it fills the panel without clipping)."""
        if self._proof_pixmap is None or self._proof_pixmap.isNull():
            return
        self._preview.setPixmap(self._proof_pixmap.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._render_proof()


def open_soft_proof(viewer: GPUImageView) -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    SoftProofDialog(viewer, str(path)).exec()
