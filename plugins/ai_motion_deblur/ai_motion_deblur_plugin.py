"""AI Motion Deblur plugin — Wiener deconvolution + optional ONNX path.

Plugin boundary justification: the ONNX path needs ``onnxruntime`` (a
heavy optional dependency) and any neural model can take seconds to
finish on CPU. Putting it inside the main viewer would risk freezing
the browse / develop loop on a bad model.
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ai_motion_deblur.deblur import (
    PSF_ANGLE_MAX,
    PSF_ANGLE_MIN,
    PSF_GAUSSIAN_RADIUS_MAX,
    PSF_GAUSSIAN_RADIUS_MIN,
    PSF_MOTION_LENGTH_MAX,
    PSF_MOTION_LENGTH_MIN,
    SNR_DB_MAX,
    SNR_DB_MIN,
    WienerOptions,
    onnx_deblur,
    wiener_deblur,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.model_dir import discover_models
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_motion_deblur")

_PLUGIN_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _PLUGIN_DIR / "models"
_PERCENT_STEPS = 100


class AIMotionDeblurPlugin(ImervuePlugin):
    plugin_name = "AI Motion Deblur"
    plugin_version = "1.0.0"
    plugin_description = "Wiener deconvolution or ONNX-based motion deblur."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "deblur_title": "AI Motion Deblur",
                "deblur_method": "Method:",
                "deblur_method_wiener_gaussian": "Wiener — Gaussian PSF",
                "deblur_method_wiener_motion": "Wiener — Motion PSF",
                "deblur_method_neural": "Neural (ONNX)",
                "deblur_gaussian_radius": "Gaussian radius:",
                "deblur_motion_length": "Motion length (px):",
                "deblur_motion_angle": "Motion angle (°):",
                "deblur_snr": "Signal-to-noise (dB):",
                "deblur_blend": "Blend with original:",
                "deblur_hint": "Drop ONNX deblur models into plugins/ai_motion_deblur/models/. "
                               "Output goes to <name>_deblur.png.",
                "deblur_done": "Saved {path}",
                "deblur_failed": "Deblur failed",
            },
            "Traditional_Chinese": {
                "deblur_title": "AI 動態模糊修復",
                "deblur_method": "方法：",
                "deblur_method_wiener_gaussian": "Wiener — 高斯 PSF",
                "deblur_method_wiener_motion": "Wiener — 運動 PSF",
                "deblur_method_neural": "神經網路（ONNX）",
                "deblur_gaussian_radius": "高斯半徑：",
                "deblur_motion_length": "運動長度（像素）：",
                "deblur_motion_angle": "運動角度（°）：",
                "deblur_snr": "訊噪比（dB）：",
                "deblur_blend": "與原圖混合：",
                "deblur_hint": "將 ONNX 去模糊模型放入 plugins/ai_motion_deblur/models/。輸出寫到 <名稱>_deblur.png。",
                "deblur_done": "已儲存 {path}",
                "deblur_failed": "去模糊失敗",
            },
            "Chinese": {
                "deblur_title": "AI 运动模糊修复",
                "deblur_method": "方法：",
                "deblur_method_wiener_gaussian": "Wiener — 高斯 PSF",
                "deblur_method_wiener_motion": "Wiener — 运动 PSF",
                "deblur_method_neural": "神经网络（ONNX）",
                "deblur_gaussian_radius": "高斯半径：",
                "deblur_motion_length": "运动长度（像素）：",
                "deblur_motion_angle": "运动角度（°）：",
                "deblur_snr": "信噪比（dB）：",
                "deblur_blend": "与原图混合：",
                "deblur_hint": "将 ONNX 去模糊模型放入 plugins/ai_motion_deblur/models/。输出保存到 <名称>_deblur.png。",
                "deblur_done": "已保存 {path}",
                "deblur_failed": "去模糊失败",
            },
            "Japanese": {
                "deblur_title": "AI モーションデブラー",
                "deblur_method": "方式:",
                "deblur_method_wiener_gaussian": "Wiener — ガウス PSF",
                "deblur_method_wiener_motion": "Wiener — モーション PSF",
                "deblur_method_neural": "ニューラル (ONNX)",
                "deblur_gaussian_radius": "ガウス半径:",
                "deblur_motion_length": "モーション長 (px):",
                "deblur_motion_angle": "モーション角度 (°):",
                "deblur_snr": "信号対雑音比 (dB):",
                "deblur_blend": "オリジナルとブレンド:",
                "deblur_hint": "ONNX デブラーモデルを plugins/ai_motion_deblur/models/ に配置してください。出力は <名前>_deblur.png に書き出されます。",
                "deblur_done": "保存しました: {path}",
                "deblur_failed": "デブラー失敗",
            },
            "Korean": {
                "deblur_title": "AI 모션 디블러",
                "deblur_method": "방법:",
                "deblur_method_wiener_gaussian": "Wiener — 가우시안 PSF",
                "deblur_method_wiener_motion": "Wiener — 모션 PSF",
                "deblur_method_neural": "신경망 (ONNX)",
                "deblur_gaussian_radius": "가우시안 반경:",
                "deblur_motion_length": "모션 길이 (px):",
                "deblur_motion_angle": "모션 각도 (°):",
                "deblur_snr": "신호 대 잡음비 (dB):",
                "deblur_blend": "원본과 혼합:",
                "deblur_hint": "ONNX 디블러 모델을 plugins/ai_motion_deblur/models/에 배치하세요. 출력은 <이름>_deblur.png에 저장됩니다.",
                "deblur_done": "{path}에 저장됨",
                "deblur_failed": "디블러 실패",
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
                            lang.get("deblur_title", "AI Motion Deblur"),
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
        AIMotionDeblurDialog(viewer, str(images[idx])).exec()


class AIMotionDeblurDialog(QDialog):
    """Pick PSF type + tweak knobs, run synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("deblur_title", "AI Motion Deblur"))
        self.setMinimumWidth(460)

        self._method = self._build_method_combo(lang)
        self._gauss_radius = _slider(PSF_GAUSSIAN_RADIUS_MIN, PSF_GAUSSIAN_RADIUS_MAX, 3)
        self._motion_length = _slider(PSF_MOTION_LENGTH_MIN, PSF_MOTION_LENGTH_MAX, 15)
        self._motion_angle = _slider(PSF_ANGLE_MIN, PSF_ANGLE_MAX, 0)
        self._snr = _slider(SNR_DB_MIN, SNR_DB_MAX, 25)
        self._blend = _slider(0, _PERCENT_STEPS, _PERCENT_STEPS)

        self._psf_pages = self._build_psf_pages(lang)
        self._method.currentIndexChanged.connect(self._on_method_changed)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())
        self._on_method_changed(0)

    def _build_method_combo(self, lang: dict) -> QComboBox:
        combo = QComboBox()
        combo.addItem(
            lang.get("deblur_method_wiener_gaussian", "Wiener — Gaussian PSF"),
            userData=("wiener", "gaussian"),
        )
        combo.addItem(
            lang.get("deblur_method_wiener_motion", "Wiener — Motion PSF"),
            userData=("wiener", "motion"),
        )
        for model_path in sorted(_discover_onnx_models()):
            combo.addItem(
                f"{lang.get('deblur_method_neural', 'Neural (ONNX)')} — {model_path.name}",
                userData=("onnx", str(model_path)),
            )
        return combo

    def _build_psf_pages(self, lang: dict) -> QStackedWidget:
        stack = QStackedWidget()
        gauss_form = QFormLayout()
        gauss_form.addRow(
            lang.get("deblur_gaussian_radius", "Gaussian radius:"),
            self._gauss_radius,
        )
        gauss_widget = QWidget()
        gauss_widget.setLayout(gauss_form)
        stack.addWidget(gauss_widget)

        motion_form = QFormLayout()
        motion_form.addRow(
            lang.get("deblur_motion_length", "Motion length (px):"),
            self._motion_length,
        )
        motion_form.addRow(
            lang.get("deblur_motion_angle", "Motion angle (°):"),
            self._motion_angle,
        )
        motion_widget = QWidget()
        motion_widget.setLayout(motion_form)
        stack.addWidget(motion_widget)

        empty = QWidget()
        empty.setLayout(QFormLayout())
        stack.addWidget(empty)
        return stack

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("deblur_method", "Method:"), self._method)
        form.addRow(self._psf_pages)
        form.addRow(lang.get("deblur_snr", "Signal-to-noise (dB):"), self._snr)
        form.addRow(lang.get("deblur_blend", "Blend with original:"), self._blend)
        return form

    def _on_method_changed(self, _idx: int) -> None:
        kind = self._method.currentData()
        if not kind:
            return
        if kind[0] == "onnx":
            self._psf_pages.setCurrentIndex(2)
            return
        self._psf_pages.setCurrentIndex(0 if kind[1] == "gaussian" else 1)

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "deblur_hint",
            "Drop ONNX deblur models into plugins/ai_motion_deblur/models/. "
            "Output goes to <name>_deblur.png.",
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
            if method[0] == "wiener":
                out_arr = wiener_deblur(arr, WienerOptions(
                    psf_kind=method[1],
                    gaussian_radius=int(self._gauss_radius.value()),
                    motion_length=int(self._motion_length.value()),
                    motion_angle=int(self._motion_angle.value()),
                    snr_db=int(self._snr.value()),
                    blend=blend,
                ))
            else:
                out_arr = onnx_deblur(arr, method[1], blend=blend)
        except (ImportError, OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_deblur.png",
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
                "deblur_failed", "Deblur failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "deblur_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _discover_onnx_models() -> list[Path]:
    """Return every .onnx file dropped into ``plugins/ai_motion_deblur/models/``.

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
