"""AI Smart Resize plugin — content-aware seam carving.

Heavy compute on large frames; the dialog blocks until the carve
finishes so the user sees the result without async wiring. The plugin
boundary keeps that compute (and any future ONNX-based saliency model)
out of the main viewer's failure path.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ai_smart_resize.seam_carving import (
    ENERGY_BOOST_MAX,
    SmartResizeOptions,
    smart_resize,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_smart_resize")

_BOOST_SLIDER_STEPS = 100
_DEFAULT_BOOST = 100  # 1.0x


class AISmartResizePlugin(ImervuePlugin):
    plugin_name = "AI Smart Resize"
    plugin_version = "1.0.0"
    plugin_description = "Content-aware resize via seam carving."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "smart_resize_title": "AI Smart Resize",
                "smart_resize_width": "Target width (px):",
                "smart_resize_height": "Target height (px):",
                "smart_resize_boost": "Subject protection:",
                "smart_resize_protect_alpha": "Protect transparent regions",
                "smart_resize_hint": "Removes / inserts low-energy seams. "
                                     "Up to ±40% of either dimension. "
                                     "Writes <name>_smart.png next to the source.",
                "smart_resize_done": "Saved {path}",
                "smart_resize_failed": "Smart resize failed",
            },
            "Traditional_Chinese": {
                "smart_resize_title": "AI 智慧縮放",
                "smart_resize_width": "目標寬度（像素）：",
                "smart_resize_height": "目標高度（像素）：",
                "smart_resize_boost": "主體保護強度：",
                "smart_resize_protect_alpha": "保護透明區域",
                "smart_resize_hint": "移除或插入低能量接縫，每個維度最多 ±40%。在來源檔旁寫出 <名稱>_smart.png。",
                "smart_resize_done": "已儲存 {path}",
                "smart_resize_failed": "智慧縮放失敗",
            },
            "Chinese": {
                "smart_resize_title": "AI 智能缩放",
                "smart_resize_width": "目标宽度（像素）：",
                "smart_resize_height": "目标高度（像素）：",
                "smart_resize_boost": "主体保护强度：",
                "smart_resize_protect_alpha": "保护透明区域",
                "smart_resize_hint": "移除或插入低能量接缝，每个维度最多 ±40%。在源文件旁写出 <名称>_smart.png。",
                "smart_resize_done": "已保存 {path}",
                "smart_resize_failed": "智能缩放失败",
            },
            "Japanese": {
                "smart_resize_title": "AI スマートリサイズ",
                "smart_resize_width": "目標幅 (px):",
                "smart_resize_height": "目標高さ (px):",
                "smart_resize_boost": "被写体保護:",
                "smart_resize_protect_alpha": "透明領域を保護",
                "smart_resize_hint": "低エネルギーのシームを削除 / 挿入します。各次元 ±40% まで。ソースの隣に <名前>_smart.png を書き出します。",
                "smart_resize_done": "保存しました: {path}",
                "smart_resize_failed": "スマートリサイズ失敗",
            },
            "Korean": {
                "smart_resize_title": "AI 스마트 리사이즈",
                "smart_resize_width": "목표 너비 (px):",
                "smart_resize_height": "목표 높이 (px):",
                "smart_resize_boost": "피사체 보호:",
                "smart_resize_protect_alpha": "투명 영역 보호",
                "smart_resize_hint": "저에너지 심을 제거 / 삽입합니다. 각 차원 ±40%까지. 원본 옆에 <이름>_smart.png를 저장합니다.",
                "smart_resize_done": "{path}에 저장됨",
                "smart_resize_failed": "스마트 리사이즈 실패",
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
                            lang.get("smart_resize_title", "AI Smart Resize"),
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
        AISmartResizeDialog(viewer, str(images[idx])).exec()


class AISmartResizeDialog(QDialog):
    """Pick target dimensions, apply seam-carving synchronously."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("smart_resize_title", "AI Smart Resize"))
        self.setMinimumWidth(440)

        size = _peek_image_size(path)
        self._src_width, self._src_height = size

        self._width = QSpinBox()
        self._width.setRange(1, 1_000_000)
        self._width.setValue(size[0])

        self._height = QSpinBox()
        self._height.setRange(1, 1_000_000)
        self._height.setValue(size[1])

        self._boost = QSlider(Qt.Orientation.Horizontal)
        self._boost.setRange(int(0.1 * _BOOST_SLIDER_STEPS),
                             int(ENERGY_BOOST_MAX * _BOOST_SLIDER_STEPS))
        self._boost.setValue(_DEFAULT_BOOST)

        self._protect_alpha = QCheckBox()
        self._protect_alpha.setChecked(True)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("smart_resize_width", "Target width (px):"), self._width)
        form.addRow(lang.get("smart_resize_height", "Target height (px):"), self._height)
        form.addRow(lang.get("smart_resize_boost", "Subject protection:"), self._boost)
        form.addRow(
            lang.get("smart_resize_protect_alpha", "Protect transparent regions"),
            self._protect_alpha,
        )
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "smart_resize_hint",
            "Removes / inserts low-energy seams. Up to ±40% of either dimension.",
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

        options = SmartResizeOptions(
            out_width=int(self._width.value()),
            out_height=int(self._height.value()),
            energy_boost=self._boost.value() / _BOOST_SLIDER_STEPS,
            protect_alpha=self._protect_alpha.isChecked(),
        )
        try:
            out_arr = smart_resize(arr, options)
        except ValueError as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_smart.png",
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
                "smart_resize_failed", "Smart resize failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "smart_resize_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def _peek_image_size(path: str) -> tuple[int, int]:
    try:
        with Image.open(path) as img:
            return img.size
    except OSError:
        return (1024, 1024)
