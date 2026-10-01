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

from ai_style_transfer.style_transfer import StyleTransferOptions, stylise
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.model_dir import discover_models
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.tool_dialog import ToolDialogMixin, Transform, slider_row

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# Style transfer runs on onnxruntime; offered for install on first use.
ONNX_PACKAGES = [("onnxruntime", "onnxruntime")]

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"

_PERCENT_STEPS = 100


class AIStyleTransferPlugin(ImervuePlugin):
    plugin_name = "AI Style Transfer"
    plugin_version = "1.0.3"
    plugin_description = "ONNX fast neural style transfer (Johnson et al.)."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "style_transfer_title": "AI Style Transfer",
                "style_transfer_model": "Style model:",
                "style_transfer_intensity": "Intensity:",
                "style_transfer_no_models": "(no models found)",
                "style_transfer_hint": "Drop ONNX style models into plugins/ai_style_transfer/models/. Output goes to <name>_styled.png.",
                "style_transfer_done": "Saved {path}",
                "style_transfer_failed": "Style transfer failed",
            },
            "Traditional_Chinese": {
                "style_transfer_title": "AI 風格轉換",
                "style_transfer_model": "風格模型：",
                "style_transfer_intensity": "強度：",
                "style_transfer_no_models": "（找不到模型）",
                "style_transfer_hint": "將 ONNX 風格模型放入 plugins/ai_style_transfer/models/。輸出寫到 <名稱>_styled.png。",
                "style_transfer_done": "已儲存 {path}",
                "style_transfer_failed": "風格轉換失敗",
            },
            "Chinese": {
                "style_transfer_title": "AI 风格迁移",
                "style_transfer_model": "风格模型：",
                "style_transfer_intensity": "强度：",
                "style_transfer_no_models": "（未找到模型）",
                "style_transfer_hint": "将 ONNX 风格模型放入 plugins/ai_style_transfer/models/。输出保存到 <名称>_styled.png。",
                "style_transfer_done": "已保存 {path}",
                "style_transfer_failed": "风格迁移失败",
            },
            "Japanese": {
                "style_transfer_title": "AI スタイル転送",
                "style_transfer_model": "スタイルモデル:",
                "style_transfer_intensity": "強度:",
                "style_transfer_no_models": "（モデルが見つかりません）",
                "style_transfer_hint": "ONNX スタイルモデルを plugins/ai_style_transfer/models/ に配置してください。出力は <名前>_styled.png に書き出されます。",
                "style_transfer_done": "保存しました: {path}",
                "style_transfer_failed": "スタイル転送失敗",
            },
            "Korean": {
                "style_transfer_title": "AI 스타일 전이",
                "style_transfer_model": "스타일 모델:",
                "style_transfer_intensity": "강도:",
                "style_transfer_no_models": "(모델을 찾을 수 없음)",
                "style_transfer_hint": "ONNX 스타일 모델을 plugins/ai_style_transfer/models/에 배치하세요. 출력은 <이름>_styled.png에 저장됩니다.",
                "style_transfer_done": "{path}에 저장됨",
                "style_transfer_failed": "스타일 전이 실패",
            },
        }

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict
        # Imervue names its Extra Tools submenus; a host that predates the
        # names has none, so the entry falls back to the Plugins menu.
        target = self.main_window.findChild(QMenu, "extra_tools.develop_submenu")
        entry = (target if target is not None else plugin_menu).addAction(
            lang.get("style_transfer_title", "AI Style Transfer"),
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
        StyleTransferDialog(viewer, str(images[idx])).exec()


class StyleTransferDialog(ToolDialogMixin, QDialog):
    """Pick model + intensity; run on a worker thread on OK."""

    output_suffix = "styled"
    failed_key = "style_transfer_failed"
    failed_text = "Style transfer failed"
    done_key = "style_transfer_done"

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
            slider_row(self._intensity, self._intensity_label),
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

    def _commit(self) -> None:
        if not self._model.currentData():
            self._notify_failure("no model selected")
            return
        super()._commit()
    def _required_packages(self) -> list[tuple[str, str]]:
        return ONNX_PACKAGES

    def _transform(self) -> Transform:
        options = StyleTransferOptions(
            model_path=str(self._model.currentData()),
            intensity=self._intensity.value() / _PERCENT_STEPS,
        )
        return lambda rgba: stylise(rgba, options)


def _discover_onnx_models() -> list[Path]:
    """Return every .onnx file dropped into ``plugins/ai_style_transfer/models/``.

    Creates the directory on first call so the user can find the
    folder in their file manager and drop weights in.
    """
    return discover_models(_MODELS_DIR)
