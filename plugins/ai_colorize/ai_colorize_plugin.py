"""AI Colorize plugin — heuristic palettes + ONNX model path.

Colourise black-and-white photos. Two methods are exposed:

* **Heuristic preset** (sepia / cool / warm / vintage) — pure-numpy LUT
  mapping; ships in the default dependency set.
* **Neural (ONNX)** — drop a colourisation model into
  ``plugins/ai_colorize/models/<name>.onnx`` and the dropdown picks it
  up. The plugin does not bundle any model files so the user controls
  what gets shipped.
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

from ai_colorize.colorize import (
    HEURISTIC_PRESETS,
    ColorizeOptions,
    heuristic_colorize,
    onnx_colorize,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_colorize")

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"

_PERCENT_STEPS = 100


class AIColorizePlugin(ImervuePlugin):
    plugin_name = "AI Colorize"
    plugin_version = "1.0.0"
    plugin_description = "Colour black-and-white photos via preset palettes or ONNX models."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "ai_colorize_title": "AI Colorize",
                "ai_colorize_method": "Method:",
                "ai_colorize_method_neural": "Neural",
                "ai_colorize_intensity": "Intensity:",
                "ai_colorize_preset_sepia": "Sepia",
                "ai_colorize_preset_cool": "Cool",
                "ai_colorize_preset_warm": "Warm",
                "ai_colorize_preset_vintage": "Vintage",
                "ai_colorize_hint": "Drop ONNX colorize models into plugins/ai_colorize/models/. Output goes to <name>_colorized.png.",
                "ai_colorize_done": "Saved {path}",
                "ai_colorize_failed": "Colorize failed",
            },
            "Traditional_Chinese": {
                "ai_colorize_title": "AI 上色",
                "ai_colorize_method": "方法：",
                "ai_colorize_method_neural": "神經網路",
                "ai_colorize_intensity": "強度：",
                "ai_colorize_preset_sepia": "棕褐",
                "ai_colorize_preset_cool": "冷色調",
                "ai_colorize_preset_warm": "暖色調",
                "ai_colorize_preset_vintage": "復古",
                "ai_colorize_hint": "將 ONNX 上色模型放入 plugins/ai_colorize/models/。輸出寫到 <名稱>_colorized.png。",
                "ai_colorize_done": "已儲存 {path}",
                "ai_colorize_failed": "上色失敗",
            },
            "Chinese": {
                "ai_colorize_title": "AI 上色",
                "ai_colorize_method": "方法：",
                "ai_colorize_method_neural": "神经网络",
                "ai_colorize_intensity": "强度：",
                "ai_colorize_preset_sepia": "棕褐",
                "ai_colorize_preset_cool": "冷色调",
                "ai_colorize_preset_warm": "暖色调",
                "ai_colorize_preset_vintage": "复古",
                "ai_colorize_hint": "将 ONNX 上色模型放入 plugins/ai_colorize/models/。输出保存到 <名称>_colorized.png。",
                "ai_colorize_done": "已保存 {path}",
                "ai_colorize_failed": "上色失败",
            },
            "Japanese": {
                "ai_colorize_title": "AI カラー化",
                "ai_colorize_method": "方式:",
                "ai_colorize_method_neural": "ニューラル",
                "ai_colorize_intensity": "強度:",
                "ai_colorize_preset_sepia": "セピア",
                "ai_colorize_preset_cool": "クール",
                "ai_colorize_preset_warm": "ウォーム",
                "ai_colorize_preset_vintage": "ビンテージ",
                "ai_colorize_hint": "ONNX カラー化モデルを plugins/ai_colorize/models/ に配置してください。出力は <名前>_colorized.png に書き出されます。",
                "ai_colorize_done": "保存しました: {path}",
                "ai_colorize_failed": "カラー化失敗",
            },
            "Korean": {
                "ai_colorize_title": "AI 채색",
                "ai_colorize_method": "방법:",
                "ai_colorize_method_neural": "신경망",
                "ai_colorize_intensity": "강도:",
                "ai_colorize_preset_sepia": "세피아",
                "ai_colorize_preset_cool": "차가운 톤",
                "ai_colorize_preset_warm": "따뜻한 톤",
                "ai_colorize_preset_vintage": "빈티지",
                "ai_colorize_hint": "ONNX 채색 모델을 plugins/ai_colorize/models/에 배치하세요. 출력은 <이름>_colorized.png에 저장됩니다.",
                "ai_colorize_done": "{path}에 저장됨",
                "ai_colorize_failed": "채색 실패",
            },
        }

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
                            lang.get("ai_colorize_title", "AI Colorize"),
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
        AIColorizeDialog(viewer, str(images[idx])).exec()


class AIColorizeDialog(QDialog):
    """Pick method + intensity, run synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("ai_colorize_title", "AI Colorize"))
        self.setMinimumWidth(440)

        self._method = QComboBox()
        # Heuristic palettes first, ONNX models afterwards.
        for preset_id in HEURISTIC_PRESETS:
            label = lang.get(f"ai_colorize_preset_{preset_id}", preset_id.title())
            self._method.addItem(label, userData=f"heuristic:{preset_id}")
        for model_path in sorted(_discover_onnx_models()):
            self._method.addItem(
                f"{lang.get('ai_colorize_method_neural', 'Neural')} — {model_path.name}",
                userData=f"onnx:{model_path}",
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
        form.addRow(lang.get("ai_colorize_method", "Method:"), self._method)
        form.addRow(
            lang.get("ai_colorize_intensity", "Intensity:"),
            _slider_with_label(self._intensity, self._intensity_label),
        )
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "ai_colorize_hint",
            "Drop ONNX colourise models into plugins/ai_colorize/models/. "
            "Output goes to <name>_colorized.png.",
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

        method_data = str(self._method.currentData())
        intensity = self._intensity.value() / _PERCENT_STEPS
        try:
            out_arr = self._dispatch(arr, method_data, intensity)
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_colorized.png",
        )
        try:
            Image.fromarray(out_arr, mode="RGBA").save(str(out_path))
        except OSError as exc:
            self._notify_failure(exc)
            return

        self._notify_success(out_path)
        self.accept()

    @staticmethod
    def _dispatch(arr: np.ndarray, method_data: str, intensity: float) -> np.ndarray:
        if method_data.startswith("heuristic:"):
            preset = method_data.split(":", 1)[1]
            return heuristic_colorize(arr, ColorizeOptions(
                method=preset, intensity=intensity,
            ))
        if method_data.startswith("onnx:"):
            model_path = method_data.split(":", 1)[1]
            return onnx_colorize(arr, model_path, intensity=intensity)
        raise ValueError(f"Unknown method data: {method_data}")

    def _notify_failure(self, exc: Exception) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            prefix = language_wrapper.language_word_dict.get(
                "ai_colorize_failed", "Colorize failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "ai_colorize_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _discover_onnx_models() -> list[Path]:
    if not _MODELS_DIR.is_dir():
        return []
    return list(_MODELS_DIR.glob("*.onnx"))


def _slider_with_label(slider: QSlider, label: QLabel) -> QWidget:
    from PySide6.QtWidgets import QHBoxLayout
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
