"""Soft proof dialog — pick an ICC profile and show the simulated preview."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.soft_proof import simulate_profile
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.soft_proof_dialog")

_PREVIEW_MAX = 640


class SoftProofDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("proof_title", "Soft Proof"))
        self.setMinimumWidth(560)

        self._profile_edit = QLineEdit()
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_profile)
        prof_row = QHBoxLayout()
        prof_row.addWidget(QLabel(lang.get("proof_profile", "ICC profile:")))
        prof_row.addWidget(self._profile_edit, 1)
        prof_row.addWidget(browse)

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
        fn, _ = QFileDialog.getOpenFileName(
            self, lang.get("proof_profile", "ICC profile"), "",
            "ICC Profiles (*.icc *.icm)",
        )
        if fn:
            self._profile_edit.setText(fn)

    def _preview_profile(self) -> None:
        lang = language_wrapper.language_word_dict
        profile = self._profile_edit.text().strip()
        if not profile:
            self._status.setText(lang.get("proof_pick", "Select an ICC profile."))
            return
        try:
            img = Image.open(self._path).convert("RGBA")
            img.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
            arr = np.asarray(img)
        except (OSError, ValueError) as err:
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
        self._preview.setPixmap(QPixmap.fromImage(qimg))
        oog = int(mask.sum())
        self._status.setText(
            lang.get("proof_oog", "Out-of-gamut pixels:") + f" {oog}",
        )


def open_soft_proof(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    SoftProofDialog(viewer, str(path)).exec()
