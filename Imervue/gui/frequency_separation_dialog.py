"""Frequency separation dialog — splits the current image into two layer files.

Unlike most develop tools, frequency separation does not write a recipe
entry. It produces two new files (``<name>_low.png`` and
``<name>_high.png``) so the user can edit them in any external editor
that supports linear-blend recombination.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.frequency_separation import (
    RADIUS_MAX,
    RADIUS_MIN,
    separate_frequencies,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.frequency_separation_dialog")


class FrequencySeparationDialog(QDialog):
    """Pick a blur radius and write the two frequency layers next to the source."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("frequency_sep_title", "Frequency Separation"))
        self.setMinimumWidth(420)

        self._radius = QSpinBox()
        self._radius.setRange(RADIUS_MIN, RADIUS_MAX)
        self._radius.setValue(8)

        hint = QLabel(
            lang.get(
                "frequency_sep_hint",
                "Writes <name>_low.png and <name>_high.png next to the source. "
                "Recombine via low + (high - 128).",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")

        form = QFormLayout()
        form.addRow(
            lang.get("frequency_sep_radius", "Blur radius:"),
            self._radius,
        )
        form.addRow(hint)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)
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
        try:
            arr = _load_image_as_rgba(self._path)
        except (OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        try:
            result = separate_frequencies(arr, radius=int(self._radius.value()))
        except ValueError as exc:
            self._notify_failure(exc)
            return

        low_path, high_path = _write_layer_files(self._path, result)
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            lang = language_wrapper.language_word_dict
            self._viewer.main_window.toast.info(
                lang.get(
                    "frequency_sep_done",
                    "Layers saved: {low}, {high}",
                ).format(low=low_path.name, high=high_path.name)
            )
        self.accept()

    def _notify_failure(self, exc: Exception) -> None:
        if not (hasattr(self._viewer, "main_window")
                and hasattr(self._viewer.main_window, "toast")):
            return
        prefix = language_wrapper.language_word_dict.get(
            "frequency_sep_failed", "Failed",
        )
        self._viewer.main_window.toast.error(f"{prefix}: {exc}")


def _load_image_as_rgba(path: str) -> np.ndarray:
    """Load ``path`` as an HxWx4 uint8 RGBA array."""
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def _write_layer_files(
    source_path: str,
    result,
) -> tuple[Path, Path]:
    """Save the low/high layers next to ``source_path`` as PNG sidecars."""
    src = Path(source_path)
    stem = src.stem
    low_path = src.with_name(f"{stem}_low.png")
    high_path = src.with_name(f"{stem}_high.png")
    Image.fromarray(result.low_frequency, mode="RGBA").save(str(low_path))
    Image.fromarray(result.high_frequency, mode="RGBA").save(str(high_path))
    return low_path, high_path


def open_frequency_separation_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    FrequencySeparationDialog(viewer, str(images[idx])).exec()
