"""AI Denoise plugin — bilateral filter or ONNX neural model.

Two methods are exposed:

* **Bilateral (fast)** — pure-numpy edge-preserving filter; ships with
  the default dependencies and works offline.
* **Neural (ONNX)** — loads a user-supplied NAFNet / DnCNN / SCUNet
  model from ``plugins/ai_denoise/models/<name>.onnx`` and runs it via
  ``onnxruntime``. The plugin does NOT bundle a model — the user drops
  one into the ``models/`` folder and the dropdown picks it up.
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
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.ai_denoise import (
    SPATIAL_RADIUS_MAX,
    SPATIAL_RADIUS_MIN,
    BilateralOptions,
    bilateral_denoise,
    onnx_denoise,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_denoise")

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"

_PERCENT_STEPS = 100


class AIDenoisePlugin(ImervuePlugin):
    plugin_name = "AI Denoise"
    plugin_version = "1.0.0"
    plugin_description = "Bilateral filter or ONNX neural denoise."
    plugin_author = "Imervue"

    def on_build_menu_bar(self, menu_bar) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        for action in menu_bar.actions():
            if action.menu() and action.text().strip() == lang.get(
                "extra_tools_menu", "Extra Tools",
            ):
                for sub_action in action.menu().actions():
                    if sub_action.menu() and sub_action.text().strip() == lang.get(
                        "retouch_submenu", "Retouch & Transform",
                    ):
                        entry = sub_action.menu().addAction(
                            lang.get("ai_denoise_title", "AI Denoise"),
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
        AIDenoiseDialog(viewer, str(images[idx])).exec()


class AIDenoiseDialog(QDialog):
    """Pick method, sliders, run synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("ai_denoise_title", "AI Denoise"))
        self.setMinimumWidth(440)

        self._method = QComboBox()
        self._method.addItem(
            lang.get("ai_denoise_method_bilateral", "Bilateral (fast)"),
            userData="bilateral",
        )
        for model_path in sorted(_discover_onnx_models()):
            self._method.addItem(
                f"{lang.get('ai_denoise_method_neural', 'Neural')} — {model_path.name}",
                userData=str(model_path),
            )

        self._radius = QSlider(Qt.Orientation.Horizontal)
        self._radius.setRange(SPATIAL_RADIUS_MIN, SPATIAL_RADIUS_MAX)
        self._radius.setValue(4)

        self._sigma = QSlider(Qt.Orientation.Horizontal)
        self._sigma.setRange(5, 100)
        self._sigma.setValue(30)

        self._blend = QSlider(Qt.Orientation.Horizontal)
        self._blend.setRange(0, _PERCENT_STEPS)
        self._blend.setValue(_PERCENT_STEPS)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("ai_denoise_method", "Method:"), self._method)
        form.addRow(lang.get("ai_denoise_radius", "Spatial radius:"), self._radius)
        form.addRow(lang.get("ai_denoise_sigma", "Intensity sigma:"), self._sigma)
        form.addRow(lang.get("ai_denoise_blend", "Blend with original:"), self._blend)
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "ai_denoise_hint",
            "Drop ONNX denoise models into plugins/ai_denoise/models/. "
            "Output goes to <name>_denoised.png.",
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
        try:
            arr = _load_rgba(self._path)
        except (OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        method = str(self._method.currentData())
        blend = self._blend.value() / _PERCENT_STEPS
        try:
            if method == "bilateral":
                out_arr = bilateral_denoise(arr, BilateralOptions(
                    spatial_radius=int(self._radius.value()),
                    intensity_sigma=float(self._sigma.value()),
                    blend=blend,
                ))
            else:
                out_arr = onnx_denoise(arr, method, blend=blend)
        except (ImportError, OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_denoised.png",
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
                "ai_denoise_failed", "Denoise failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "ai_denoise_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _discover_onnx_models() -> list[Path]:
    """Return every .onnx file dropped into ``plugins/ai_denoise/models/``."""
    if not _MODELS_DIR.is_dir():
        return []
    return list(_MODELS_DIR.glob("*.onnx"))


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
