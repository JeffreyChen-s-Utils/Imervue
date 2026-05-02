"""AI Portrait Relighting plugin — heuristic shading + optional ONNX path."""
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

from ai_portrait_relight.relight import (
    AZIMUTH_MAX,
    AZIMUTH_MIN,
    ELEVATION_MAX,
    ELEVATION_MIN,
    INTENSITY_MAX,
    INTENSITY_MIN,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    RelightOptions,
    heuristic_relight,
    onnx_relight,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.model_dir import discover_models
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_portrait_relight")

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"
_PERCENT_STEPS = 100
_INTENSITY_STEPS = 100  # slider int -> intensity = value / 100


class AIPortraitRelightPlugin(ImervuePlugin):
    plugin_name = "AI Portrait Relighting"
    plugin_version = "1.0.0"
    plugin_description = "Heuristic directional relighting + optional ONNX path."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "relight_title": "AI Portrait Relighting",
                "relight_method": "Method:",
                "relight_method_heuristic": "Heuristic (numpy)",
                "relight_method_neural": "Neural (ONNX)",
                "relight_azimuth": "Light azimuth (°):",
                "relight_elevation": "Light elevation (°):",
                "relight_intensity": "Intensity:",
                "relight_temperature": "Temperature (cool ↔ warm):",
                "relight_blend": "Blend with original:",
                "relight_hint": "Drop ONNX relight models into plugins/ai_portrait_relight/models/. "
                                "Output goes to <name>_relit.png.",
                "relight_done": "Saved {path}",
                "relight_failed": "Relight failed",
            },
            "Traditional_Chinese": {
                "relight_title": "AI 肖像重打光",
                "relight_method": "方法：",
                "relight_method_heuristic": "啟發式（numpy）",
                "relight_method_neural": "神經網路（ONNX）",
                "relight_azimuth": "光源方位角（°）：",
                "relight_elevation": "光源仰角（°）：",
                "relight_intensity": "強度：",
                "relight_temperature": "色溫（冷 ↔ 暖）：",
                "relight_blend": "與原圖混合：",
                "relight_hint": "將 ONNX 重打光模型放入 plugins/ai_portrait_relight/models/。輸出寫到 <名稱>_relit.png。",
                "relight_done": "已儲存 {path}",
                "relight_failed": "重打光失敗",
            },
            "Chinese": {
                "relight_title": "AI 肖像重打光",
                "relight_method": "方法：",
                "relight_method_heuristic": "启发式（numpy）",
                "relight_method_neural": "神经网络（ONNX）",
                "relight_azimuth": "光源方位角（°）：",
                "relight_elevation": "光源仰角（°）：",
                "relight_intensity": "强度：",
                "relight_temperature": "色温（冷 ↔ 暖）：",
                "relight_blend": "与原图混合：",
                "relight_hint": "将 ONNX 重打光模型放入 plugins/ai_portrait_relight/models/。输出保存到 <名称>_relit.png。",
                "relight_done": "已保存 {path}",
                "relight_failed": "重打光失败",
            },
            "Japanese": {
                "relight_title": "AI ポートレートリライト",
                "relight_method": "方式:",
                "relight_method_heuristic": "ヒューリスティック (numpy)",
                "relight_method_neural": "ニューラル (ONNX)",
                "relight_azimuth": "光源の方位角 (°):",
                "relight_elevation": "光源の仰角 (°):",
                "relight_intensity": "強度:",
                "relight_temperature": "色温度 (寒色 ↔ 暖色):",
                "relight_blend": "オリジナルとブレンド:",
                "relight_hint": "ONNX リライトモデルを plugins/ai_portrait_relight/models/ に配置してください。出力は <名前>_relit.png に書き出されます。",
                "relight_done": "保存しました: {path}",
                "relight_failed": "リライト失敗",
            },
            "Korean": {
                "relight_title": "AI 인물 리라이팅",
                "relight_method": "방법:",
                "relight_method_heuristic": "휴리스틱 (numpy)",
                "relight_method_neural": "신경망 (ONNX)",
                "relight_azimuth": "광원 방위각 (°):",
                "relight_elevation": "광원 고도 (°):",
                "relight_intensity": "강도:",
                "relight_temperature": "색온도 (차가움 ↔ 따뜻함):",
                "relight_blend": "원본과 혼합:",
                "relight_hint": "ONNX 리라이트 모델을 plugins/ai_portrait_relight/models/에 배치하세요. 출력은 <이름>_relit.png에 저장됩니다.",
                "relight_done": "{path}에 저장됨",
                "relight_failed": "리라이트 실패",
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
                        "retouch_submenu", "Retouch & Transform",
                    ):
                        entry = sub_action.menu().addAction(
                            lang.get("relight_title", "AI Portrait Relighting"),
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
        AIPortraitRelightDialog(viewer, str(images[idx])).exec()


class AIPortraitRelightDialog(QDialog):
    """Pick method + light direction, run synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("relight_title", "AI Portrait Relighting"))
        self.setMinimumWidth(440)

        self._method = self._build_method_combo(lang)
        self._azimuth = _slider(AZIMUTH_MIN, AZIMUTH_MAX, 45)
        self._elevation = _slider(ELEVATION_MIN, ELEVATION_MAX, 30)
        self._intensity = _slider(
            int(INTENSITY_MIN * _INTENSITY_STEPS),
            int(INTENSITY_MAX * _INTENSITY_STEPS),
            60,
        )
        self._temperature = _slider(TEMPERATURE_MIN, TEMPERATURE_MAX, 0)
        self._blend = _slider(0, _PERCENT_STEPS, _PERCENT_STEPS)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_method_combo(self, lang: dict) -> QComboBox:
        combo = QComboBox()
        combo.addItem(
            lang.get("relight_method_heuristic", "Heuristic (numpy)"),
            userData=("heuristic", None),
        )
        for model_path in sorted(_discover_onnx_models()):
            combo.addItem(
                f"{lang.get('relight_method_neural', 'Neural (ONNX)')} — {model_path.name}",
                userData=("onnx", str(model_path)),
            )
        return combo

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("relight_method", "Method:"), self._method)
        form.addRow(lang.get("relight_azimuth", "Light azimuth (°):"), self._azimuth)
        form.addRow(lang.get("relight_elevation", "Light elevation (°):"), self._elevation)
        form.addRow(lang.get("relight_intensity", "Intensity:"), self._intensity)
        form.addRow(
            lang.get("relight_temperature", "Temperature (cool ↔ warm):"),
            self._temperature,
        )
        form.addRow(lang.get("relight_blend", "Blend with original:"), self._blend)
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "relight_hint",
            "Drop ONNX relight models into plugins/ai_portrait_relight/models/. "
            "Output goes to <name>_relit.png.",
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

        method = self._method.currentData()
        blend = self._blend.value() / _PERCENT_STEPS

        try:
            if method[0] == "heuristic":
                out_arr = heuristic_relight(arr, RelightOptions(
                    azimuth=float(self._azimuth.value()),
                    elevation=float(self._elevation.value()),
                    intensity=self._intensity.value() / _INTENSITY_STEPS,
                    temperature=int(self._temperature.value()),
                    blend=blend,
                ))
            else:
                out_arr = onnx_relight(arr, method[1], blend=blend)
        except (ImportError, OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_relit.png",
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
                "relight_failed", "Relight failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "relight_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _discover_onnx_models() -> list[Path]:
    """Return every .onnx file dropped into ``plugins/ai_portrait_relight/models/``.

    Creates the directory on first call so the user can find the
    folder in their file manager and drop weights in.
    """
    return discover_models(_MODELS_DIR)


def _slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    return s


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
