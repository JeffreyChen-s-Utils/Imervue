"""AI Style Transfer plugin — ONNX fast neural style transfer.

Auto-discovers any ``.onnx`` model dropped into
``plugins/ai_style_transfer/models/``. Each ONNX file becomes one entry
in the dialog dropdown, so users can ship multiple style models (one
per painting style: candy, mosaic, rain_princess, udnie, …) and switch
between them from a single dialog.

The pure inference logic lives in ``style_transfer.py`` inside the same
plugin package — main program code does not import any of it, per the
plugins-vs-main rule in CLAUDE.md.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ai_style_transfer.style_transfer import StyleTransferOptions, stylise
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_style_transfer")

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"

_PERCENT_STEPS = 100


class AIStyleTransferPlugin(ImervuePlugin):
    plugin_name = "AI Style Transfer"
    plugin_version = "1.0.0"
    plugin_description = "ONNX fast neural style transfer (Johnson et al.)."
    plugin_author = "Imervue"

    def on_build_menu_bar(self, menu_bar) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        for action in menu_bar.actions():
            if action.menu() and action.text().strip() == lang.get(
                "extra_tools_menu", "Extra Tools",
            ):
                for sub_action in action.menu().actions():
                    if sub_action.menu() and sub_action.text().strip() == lang.get(
                        "develop_submenu", "Develop (Non-Destructive)",
                    ):
                        entry = sub_action.menu().addAction(
                            lang.get("style_transfer_title", "AI Style Transfer"),
                        )
                        entry.triggered.connect(self._open_dialog)
                        return

    def _open_dialog(self) -> None:
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return
        images = list(getattr(viewer.model, "images", []))
        idx = getattr(viewer, "current_index", -1)
        if not (0 <= idx < len(images)):
            return
        StyleTransferDialog(viewer, str(images[idx])).exec()


class StyleTransferDialog(QDialog):
    """Pick model + intensity, run synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("style_transfer_title", "AI Style Transfer"))
        self.setMinimumWidth(440)

        self._model = QComboBox()
        models = _discover_onnx_models()
        for model_path in sorted(models):
            self._model.addItem(model_path.stem, userData=str(model_path))
        if not models:
            self._model.addItem(
                lang.get("style_transfer_no_models", "(no models found)"),
                userData="",
            )

        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, _PERCENT_STEPS)
        self._intensity.setValue(_PERCENT_STEPS)
        self._intensity_label = QLabel("100%")
        self._intensity.valueChanged.connect(
            lambda v: self._intensity_label.setText(f"{v}%"),
        )

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("style_transfer_model", "Style model:"), self._model)
        form.addRow(
            lang.get("style_transfer_intensity", "Intensity:"),
            _slider_with_label(self._intensity, self._intensity_label),
        )
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "style_transfer_hint",
            "Drop ONNX style models into plugins/ai_style_transfer/models/. "
            "Output goes to <name>_styled.png.",
        )
        hint = QLabel(msg)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        return hint

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
        model_path = str(self._model.currentData() or "")
        if not model_path:
            self._notify_failure(RuntimeError("no model selected"))
            return
        try:
            arr = _load_rgba(self._path)
        except (OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        options = StyleTransferOptions(
            model_path=model_path,
            intensity=self._intensity.value() / _PERCENT_STEPS,
        )
        try:
            out_arr = stylise(arr, options)
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_styled.png",
        )
        try:
            Image.fromarray(out_arr, mode="RGBA").save(str(out_path))
        except OSError as exc:
            self._notify_failure(exc)
            return

        self._notify_success(out_path)
        self.accept()

    def _notify_failure(self, exc: Exception) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            prefix = language_wrapper.language_word_dict.get(
                "style_transfer_failed", "Style transfer failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "style_transfer_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _discover_onnx_models() -> list[Path]:
    if not _MODELS_DIR.is_dir():
        return []
    return list(_MODELS_DIR.glob("*.onnx"))


def _slider_with_label(slider: QSlider, label: QLabel) -> QWidget:
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, stretch=1)
    label.setMinimumWidth(50)
    row.addWidget(label)
    return container


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
