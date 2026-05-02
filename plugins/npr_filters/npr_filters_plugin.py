"""NPR Filters plugin — pencil / oil / watercolour / line-art styles.

The plugin lives outside the main package because OpenCV is an optional
runtime dependency. ``cv2`` is imported lazily inside the algorithm
helpers so the plugin's import / discovery path stays cheap and only
fails at "Apply" time if OpenCV is missing.
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

from npr_filters.filters import (
    INTENSITY_MAX,
    LINE_THRESHOLD_MAX,
    LINE_THRESHOLD_MIN,
    OIL_LEVELS_MAX,
    OIL_LEVELS_MIN,
    SIGMA_R_MAX,
    SIGMA_R_MIN,
    SIGMA_S_MAX,
    SIGMA_S_MIN,
    NPRFilterOptions,
    apply_npr_filter,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.npr_filters")

_PERCENT_STEPS = 100
_DEFAULT_INTENSITY = 100
_DEFAULT_SIGMA_S = 60
_DEFAULT_SIGMA_R = 45
_DEFAULT_OIL_LEVELS = 8
_DEFAULT_LINE_THRESHOLD = 80


class NPRFiltersPlugin(ImervuePlugin):
    plugin_name = "NPR Filters"
    plugin_version = "1.0.0"
    plugin_description = "Pencil sketch, oil painting, watercolour and line-art styles."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "npr_filters_title": "NPR Style Filters",
                "npr_filters_style": "Style:",
                "npr_filters_style_pencil_sketch": "Pencil sketch",
                "npr_filters_style_oil_painting": "Oil painting",
                "npr_filters_style_watercolor": "Watercolour",
                "npr_filters_style_line_art": "Line art",
                "npr_filters_intensity": "Blend with original:",
                "npr_filters_sigma_s": "Spatial scale:",
                "npr_filters_sigma_r": "Detail / range:",
                "npr_filters_oil_levels": "Posterise levels:",
                "npr_filters_line_threshold": "Edge threshold:",
                "npr_filters_hint": "Writes <name>_npr.png next to the source. Requires opencv-python.",
                "npr_filters_done": "Saved {path}",
                "npr_filters_failed": "NPR filter failed",
            },
            "Traditional_Chinese": {
                "npr_filters_title": "NPR 風格濾鏡",
                "npr_filters_style": "風格：",
                "npr_filters_style_pencil_sketch": "鉛筆素描",
                "npr_filters_style_oil_painting": "油畫",
                "npr_filters_style_watercolor": "水彩",
                "npr_filters_style_line_art": "線稿",
                "npr_filters_intensity": "與原圖混合：",
                "npr_filters_sigma_s": "空間尺度：",
                "npr_filters_sigma_r": "細節 / 範圍：",
                "npr_filters_oil_levels": "色階數：",
                "npr_filters_line_threshold": "邊緣門檻：",
                "npr_filters_hint": "在來源檔旁寫出 <名稱>_npr.png。需要 opencv-python。",
                "npr_filters_done": "已儲存 {path}",
                "npr_filters_failed": "NPR 濾鏡失敗",
            },
            "Chinese": {
                "npr_filters_title": "NPR 风格滤镜",
                "npr_filters_style": "风格：",
                "npr_filters_style_pencil_sketch": "铅笔素描",
                "npr_filters_style_oil_painting": "油画",
                "npr_filters_style_watercolor": "水彩",
                "npr_filters_style_line_art": "线稿",
                "npr_filters_intensity": "与原图混合：",
                "npr_filters_sigma_s": "空间尺度：",
                "npr_filters_sigma_r": "细节 / 范围：",
                "npr_filters_oil_levels": "色阶数：",
                "npr_filters_line_threshold": "边缘阈值：",
                "npr_filters_hint": "在源文件旁写出 <名称>_npr.png。需要 opencv-python。",
                "npr_filters_done": "已保存 {path}",
                "npr_filters_failed": "NPR 滤镜失败",
            },
            "Japanese": {
                "npr_filters_title": "NPR スタイルフィルター",
                "npr_filters_style": "スタイル:",
                "npr_filters_style_pencil_sketch": "鉛筆スケッチ",
                "npr_filters_style_oil_painting": "油絵",
                "npr_filters_style_watercolor": "水彩",
                "npr_filters_style_line_art": "線画",
                "npr_filters_intensity": "オリジナルとブレンド:",
                "npr_filters_sigma_s": "空間スケール:",
                "npr_filters_sigma_r": "ディテール / レンジ:",
                "npr_filters_oil_levels": "ポスタリゼーション階調:",
                "npr_filters_line_threshold": "エッジ閾値:",
                "npr_filters_hint": "ソースの隣に <名前>_npr.png を書き出します。opencv-python が必要です。",
                "npr_filters_done": "保存しました: {path}",
                "npr_filters_failed": "NPR フィルター失敗",
            },
            "Korean": {
                "npr_filters_title": "NPR 스타일 필터",
                "npr_filters_style": "스타일:",
                "npr_filters_style_pencil_sketch": "연필 스케치",
                "npr_filters_style_oil_painting": "유화",
                "npr_filters_style_watercolor": "수채화",
                "npr_filters_style_line_art": "라인 아트",
                "npr_filters_intensity": "원본과 혼합:",
                "npr_filters_sigma_s": "공간 스케일:",
                "npr_filters_sigma_r": "디테일 / 범위:",
                "npr_filters_oil_levels": "포스터화 레벨:",
                "npr_filters_line_threshold": "에지 임계값:",
                "npr_filters_hint": "원본 옆에 <이름>_npr.png를 저장합니다. opencv-python이 필요합니다.",
                "npr_filters_done": "{path}에 저장됨",
                "npr_filters_failed": "NPR 필터 실패",
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
                            lang.get("npr_filters_title", "NPR Style Filters"),
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
        NPRFiltersDialog(viewer, str(images[idx])).exec()


class NPRFiltersDialog(QDialog):
    """Pick a style + tweak its dedicated knobs, run synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("npr_filters_title", "NPR Style Filters"))
        self.setMinimumWidth(440)

        self._style = self._build_style_combo(lang)
        self._intensity = self._build_slider(0, _PERCENT_STEPS, _DEFAULT_INTENSITY)
        self._sigma_s = self._build_slider(SIGMA_S_MIN, SIGMA_S_MAX, _DEFAULT_SIGMA_S)
        self._sigma_r = self._build_slider(SIGMA_R_MIN, SIGMA_R_MAX, _DEFAULT_SIGMA_R)
        self._oil_levels = self._build_slider(
            OIL_LEVELS_MIN, OIL_LEVELS_MAX, _DEFAULT_OIL_LEVELS,
        )
        self._line_threshold = self._build_slider(
            LINE_THRESHOLD_MIN, LINE_THRESHOLD_MAX, _DEFAULT_LINE_THRESHOLD,
        )

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    @staticmethod
    def _build_style_combo(lang: dict) -> QComboBox:
        combo = QComboBox()
        for style_id, key, fallback in (
            ("pencil_sketch", "npr_filters_style_pencil_sketch", "Pencil sketch"),
            ("oil_painting", "npr_filters_style_oil_painting", "Oil painting"),
            ("watercolor", "npr_filters_style_watercolor", "Watercolour"),
            ("line_art", "npr_filters_style_line_art", "Line art"),
        ):
            combo.addItem(lang.get(key, fallback), userData=style_id)
        return combo

    @staticmethod
    def _build_slider(lo: int, hi: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        return slider

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("npr_filters_style", "Style:"), self._style)
        form.addRow(lang.get("npr_filters_intensity", "Blend with original:"),
                    self._intensity)
        form.addRow(lang.get("npr_filters_sigma_s", "Spatial scale:"), self._sigma_s)
        form.addRow(lang.get("npr_filters_sigma_r", "Detail / range:"), self._sigma_r)
        form.addRow(lang.get("npr_filters_oil_levels", "Posterise levels:"),
                    self._oil_levels)
        form.addRow(lang.get("npr_filters_line_threshold", "Edge threshold:"),
                    self._line_threshold)
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "npr_filters_hint",
            "Writes <name>_npr.png next to the source. Requires opencv-python.",
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

        intensity = self._intensity.value() / _PERCENT_STEPS
        intensity = max(0.0, min(INTENSITY_MAX, intensity))

        options = NPRFilterOptions(
            style=str(self._style.currentData()),
            intensity=intensity,
            sigma_s=int(self._sigma_s.value()),
            sigma_r=int(self._sigma_r.value()),
            oil_levels=int(self._oil_levels.value()),
            line_threshold=int(self._line_threshold.value()),
        )
        try:
            out_arr = apply_npr_filter(arr, options)
        except (ImportError, ValueError) as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_npr.png",
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
                "npr_filters_failed", "NPR filter failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "npr_filters_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
