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

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QMenu,
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
from Imervue.plugin.model_dir import discover_models
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.tool_dialog import ToolDialogMixin, Transform, slider_row

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# The optional ONNX path needs onnxruntime; offered for install on first use.
ONNX_PACKAGES = [("onnxruntime", "onnxruntime")]

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"

_PERCENT_STEPS = 100


class AIColorizePlugin(ImervuePlugin):
    plugin_name = "AI Colorize"
    plugin_version = "1.0.3"
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

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict
        # Imervue names its Extra Tools submenus; a host that predates the
        # names has none, so the entry falls back to the Plugins menu.
        target = self.main_window.findChild(QMenu, "extra_tools.develop_submenu")
        entry = (target if target is not None else plugin_menu).addAction(
            lang.get("ai_colorize_title", "AI Colorize"),
        )
        entry.triggered.connect(self._open_dialog)

    def _open_dialog(self) -> None:
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return
        images = list(getattr(viewer.model, "images", []))
        idx = getattr(viewer, "current_index", -1)
        if not (0 <= idx < len(images)):
            return
        AIColorizeDialog(viewer, str(images[idx])).exec()


class AIColorizeDialog(ToolDialogMixin, QDialog):
    """Pick method + intensity; run on a worker thread on OK."""

    output_suffix = "colorized"
    failed_key = "ai_colorize_failed"
    failed_text = "Colorize failed"
    done_key = "ai_colorize_done"

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
            slider_row(self._intensity, self._intensity_label),
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

    def _required_packages(self) -> list[tuple[str, str]]:
        # The ONNX path needs onnxruntime; the mixin offers to install it before running.
        return ONNX_PACKAGES if str(self._method.currentData()).startswith("onnx:") else []
    def _transform(self) -> Transform:
        method_data = str(self._method.currentData())
        intensity = self._intensity.value() / _PERCENT_STEPS
        return lambda rgba: _colorize_dispatch(rgba, method_data, intensity)


def _discover_onnx_models() -> list[Path]:
    """Return every .onnx file dropped into ``plugins/ai_colorize/models/``.

    Creates the directory on first call so the user can find the
    folder in their file manager and drop weights in.
    """
    return discover_models(_MODELS_DIR)


def _colorize_dispatch(arr: np.ndarray, method_data: str,
                       intensity: float) -> np.ndarray:
    if method_data.startswith("heuristic:"):
        preset = method_data.split(":", 1)[1]
        return heuristic_colorize(arr, ColorizeOptions(
            method=preset, intensity=intensity,
        ))
    if method_data.startswith("onnx:"):
        model_path = method_data.split(":", 1)[1]
        return onnx_colorize(arr, model_path, intensity=intensity)
    raise ValueError(f"Unknown method data: {method_data}")
