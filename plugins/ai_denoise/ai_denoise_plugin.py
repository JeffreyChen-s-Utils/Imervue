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

from pathlib import Path
from typing import TYPE_CHECKING

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

from ai_denoise.denoise import (
    SPATIAL_RADIUS_MAX,
    SPATIAL_RADIUS_MIN,
    BilateralOptions,
    bilateral_denoise,
    onnx_denoise,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.model_dir import discover_models
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.tool_dialog import ToolDialogMixin, Transform

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# The optional ONNX path needs onnxruntime; offered for install on first use.
ONNX_PACKAGES = [("onnxruntime", "onnxruntime")]

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"

_PERCENT_STEPS = 100


class AIDenoisePlugin(ImervuePlugin):
    plugin_name = "AI Denoise"
    plugin_version = "1.0.3"
    plugin_description = "Bilateral filter or ONNX neural denoise."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "ai_denoise_title": "AI Denoise",
                "ai_denoise_method": "Method:",
                "ai_denoise_method_bilateral": "Bilateral (fast)",
                "ai_denoise_method_neural": "Neural",
                "ai_denoise_radius": "Spatial radius:",
                "ai_denoise_sigma": "Intensity sigma:",
                "ai_denoise_blend": "Blend with original:",
                "ai_denoise_hint": "Drop ONNX denoise models into plugins/ai_denoise/models/. Output goes to <name>_denoised.png.",
                "ai_denoise_done": "Saved {path}",
                "ai_denoise_failed": "Denoise failed",
            },
            "Traditional_Chinese": {
                "ai_denoise_title": "AI 降噪",
                "ai_denoise_method": "方法：",
                "ai_denoise_method_bilateral": "雙邊濾波（快速）",
                "ai_denoise_method_neural": "神經網路",
                "ai_denoise_radius": "空間半徑：",
                "ai_denoise_sigma": "強度 sigma：",
                "ai_denoise_blend": "與原圖混合：",
                "ai_denoise_hint": "將 ONNX 降噪模型放入 plugins/ai_denoise/models/。輸出寫到 <名稱>_denoised.png。",
                "ai_denoise_done": "已儲存 {path}",
                "ai_denoise_failed": "降噪失敗",
            },
            "Chinese": {
                "ai_denoise_title": "AI 降噪",
                "ai_denoise_method": "方法：",
                "ai_denoise_method_bilateral": "双边滤波（快速）",
                "ai_denoise_method_neural": "神经网络",
                "ai_denoise_radius": "空间半径：",
                "ai_denoise_sigma": "强度 sigma：",
                "ai_denoise_blend": "与原图混合：",
                "ai_denoise_hint": "将 ONNX 降噪模型放入 plugins/ai_denoise/models/。输出保存到 <名称>_denoised.png。",
                "ai_denoise_done": "已保存 {path}",
                "ai_denoise_failed": "降噪失败",
            },
            "Japanese": {
                "ai_denoise_title": "AI ノイズ除去",
                "ai_denoise_method": "方式:",
                "ai_denoise_method_bilateral": "バイラテラル（高速）",
                "ai_denoise_method_neural": "ニューラル",
                "ai_denoise_radius": "空間半径:",
                "ai_denoise_sigma": "強度 sigma:",
                "ai_denoise_blend": "オリジナルとブレンド:",
                "ai_denoise_hint": "ONNX デノイズモデルを plugins/ai_denoise/models/ に配置してください。出力は <名前>_denoised.png に書き出されます。",
                "ai_denoise_done": "保存しました: {path}",
                "ai_denoise_failed": "デノイズ失敗",
            },
            "Korean": {
                "ai_denoise_title": "AI 노이즈 제거",
                "ai_denoise_method": "방법:",
                "ai_denoise_method_bilateral": "양방향 필터(빠름)",
                "ai_denoise_method_neural": "신경망",
                "ai_denoise_radius": "공간 반경:",
                "ai_denoise_sigma": "강도 sigma:",
                "ai_denoise_blend": "원본과 혼합:",
                "ai_denoise_hint": "ONNX 노이즈 제거 모델을 plugins/ai_denoise/models/에 배치하세요. 출력은 <이름>_denoised.png에 저장됩니다.",
                "ai_denoise_done": "{path}에 저장됨",
                "ai_denoise_failed": "노이즈 제거 실패",
            },
        }

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict
        # Imervue names its Extra Tools submenus; a host that predates the
        # names has none, so the entry falls back to the Plugins menu.
        target = self.main_window.findChild(QMenu, "extra_tools.retouch_submenu")
        entry = (target if target is not None else plugin_menu).addAction(
            lang.get("ai_denoise_title", "AI Denoise"),
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
        AIDenoiseDialog(viewer, str(images[idx])).exec()


class AIDenoiseDialog(ToolDialogMixin, QDialog):
    """Pick method, sliders; run on a worker thread on OK."""

    output_suffix = "denoised"
    failed_key = "ai_denoise_failed"
    failed_text = "Denoise failed"
    done_key = "ai_denoise_done"

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

    def _required_packages(self) -> list[tuple[str, str]]:
        # The ONNX path needs onnxruntime; the mixin offers to install it before running.
        return ONNX_PACKAGES if str(self._method.currentData()) != "bilateral" else []
    def _transform(self) -> Transform:
        method = str(self._method.currentData())
        blend = self._blend.value() / _PERCENT_STEPS
        if method != "bilateral":
            return lambda rgba: onnx_denoise(rgba, method, blend=blend)
        options = BilateralOptions(
            spatial_radius=int(self._radius.value()),
            intensity_sigma=float(self._sigma.value()),
            blend=blend,
        )
        return lambda rgba: bilateral_denoise(rgba, options)


def _discover_onnx_models() -> list[Path]:
    """Return every .onnx file dropped into ``plugins/ai_denoise/models/``.

    Creates the directory on first call so the user can find the
    folder in their file manager and drop weights in.
    """
    return discover_models(_MODELS_DIR)
