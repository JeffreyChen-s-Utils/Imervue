"""AI Object Remove plugin — click an object, flood-fill it, inpaint it away.

The plugin adds a *Remove Object* entry to the Plugin menu. The user clicks the
object in a preview, a colour-similar region floods into a mask, and the masked
region is filled by the model-free diffusion inpainter. The heavy generative
path (LaMa/ONNX) can be added later behind the same plugin without touching the
main viewer.

Pure logic lives in :mod:`ai_object_remove.object_removal`; this module is the
Qt shell, so its drawing/event code carries ``# pragma: no cover``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ai_object_remove.object_removal import (
    GROW_MAX,
    TOLERANCE_MAX,
    build_mask,
    grow_mask,
    image_coord_from_click,
    onnx_inpaint,
    remove_object,
)
from ai_object_remove.sam import discover_sam_models, sam_mask
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.model_dir import discover_models
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_object_remove")

_MODELS_DIR = Path(__file__).resolve().parent / "models"
_PREVIEW_W = 480
_PREVIEW_H = 360
_PREVIEW_DEBOUNCE_MS = 150
_RGB_STRIDE = 3
_DEFAULT_TOLERANCE = 32
_DEFAULT_GROW = 2
_OVERLAY_RGB = np.array([255, 40, 40], dtype=np.float32)
_OVERLAY_ALPHA = 0.55


class AIObjectRemovePlugin(ImervuePlugin):
    plugin_name = "AI Object Remove"
    plugin_version = "1.0.0"
    plugin_description = "Click an object to flood-select and inpaint it away."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return _TRANSLATIONS

    def on_build_menu_bar(self, plugin_menu) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        action = plugin_menu.addAction(lang.get("object_remove_title", "Remove Object"))
        action.triggered.connect(self._open_dialog)

    def _open_dialog(self) -> None:  # pragma: no cover - Qt UI
        viewer = getattr(self, "viewer", None)
        images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
        idx = getattr(viewer, "current_index", -1)
        if not (0 <= idx < len(images)):
            return
        ObjectRemoveDialog(viewer, str(images[idx])).exec()


class _ClickLabel(QLabel):
    """A QLabel that reports left-click positions in widget coordinates."""

    clicked = Signal(float, float)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.clicked.emit(pos.x(), pos.y())
            event.accept()
            return
        super().mousePressEvent(event)


class ObjectRemoveDialog(QDialog):
    """Click an object, preview the mask, and inpaint it away on Apply."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._arr = _load_rgba(path)
        self._seed: tuple[int, int] | None = None
        self._mask: np.ndarray | None = None
        self._worker: _RemoveWorker | None = None
        self._sam_worker: _SamMaskWorker | None = None
        self._sam_encoder, self._sam_decoder = discover_sam_models(_MODELS_DIR)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("object_remove_title", "Remove Object"))

        self._selection = QComboBox()
        self._selection.addItem(
            lang.get("object_remove_selection_flood", "Flood-fill (fast)"),
            userData="flood",
        )
        if self._sam_encoder and self._sam_decoder:
            self._selection.addItem(
                lang.get("object_remove_selection_sam", "SAM (precise)"),
                userData="sam",
            )

        self._preview = _ClickLabel()
        self._preview.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.clicked.connect(self._on_click)

        self._tolerance = QSlider(Qt.Orientation.Horizontal)
        self._tolerance.setRange(0, TOLERANCE_MAX)
        self._tolerance.setValue(_DEFAULT_TOLERANCE)
        self._grow = QSlider(Qt.Orientation.Horizontal)
        self._grow.setRange(0, GROW_MAX)
        self._grow.setValue(_DEFAULT_GROW)

        self._method = QComboBox()
        self._method.addItem(
            lang.get("object_remove_method_diffusion", "Diffusion (fast)"),
            userData=None,
        )
        for model_path in sorted(discover_models(_MODELS_DIR)):
            self._method.addItem(model_path.name, userData=str(model_path))

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._recompute_mask)
        self._tolerance.valueChanged.connect(self._on_param_changed)
        self._grow.valueChanged.connect(self._on_param_changed)

        self._build_layout(lang)
        self._render_preview()

    def _build_layout(self, lang: dict) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._preview)
        layout.addWidget(self._build_hint(lang))
        layout.addWidget(QLabel(lang.get("object_remove_selection", "Selection:")))
        layout.addWidget(self._selection)
        layout.addWidget(QLabel(lang.get("object_remove_tolerance", "Tolerance:")))
        layout.addWidget(self._tolerance)
        layout.addWidget(QLabel(lang.get("object_remove_grow", "Grow edge:")))
        layout.addWidget(self._grow)
        layout.addWidget(QLabel(lang.get("object_remove_method", "Method:")))
        layout.addWidget(self._method)
        layout.addWidget(self._build_models_hint(lang))
        layout.addLayout(self._build_buttons(lang))

    @staticmethod
    def _build_models_hint(lang: dict) -> QLabel:
        hint = QLabel(lang.get(
            "object_remove_models_hint",
            "Drop LaMa/ONNX inpaint models into plugins/ai_object_remove/models/.",
        ))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        return hint

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        hint = QLabel(lang.get(
            "object_remove_hint",
            "Click the object to select it, adjust tolerance, then Apply.",
        ))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        return hint

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton(lang.get("object_remove_apply", "Apply"))
        apply_btn.clicked.connect(self._commit)
        row.addWidget(cancel)
        row.addWidget(apply_btn)
        return row

    # -- selection ----------------------------------------------------------

    def _on_click(self, wx: float, wy: float) -> None:
        coord = image_coord_from_click(
            wx, wy, self._preview.width(), self._preview.height(),
            self._arr.shape[1], self._arr.shape[0],
        )
        if coord is None:
            return
        self._seed = coord
        if self._selection.currentData() == "sam" and self._sam_encoder and self._sam_decoder:
            self._run_sam(coord)
        else:
            self._recompute_mask()

    def _on_param_changed(self, _value: int) -> None:  # pragma: no cover - Qt UI
        if self._seed is not None and self._selection.currentData() != "sam":
            self._debounce.start(_PREVIEW_DEBOUNCE_MS)

    def _run_sam(self, coord: tuple[int, int]) -> None:  # pragma: no cover - Qt UI
        if self._sam_worker is not None:
            return
        self._sam_worker = _SamMaskWorker(
            self._arr, coord, self._sam_encoder, self._sam_decoder,
        )
        self._sam_worker.done.connect(self._on_sam_done)
        self._sam_worker.start()

    def _on_sam_done(self, ok: bool, mask_or_error: object) -> None:  # pragma: no cover - Qt UI
        self._sam_worker = None
        if not ok:
            self._notify("object_remove_failed", "Object removal failed", str(mask_or_error))
            return
        mask = mask_or_error
        self._mask = grow_mask(mask, self._grow.value()) if self._grow.value() else mask
        self._render_preview()

    def _recompute_mask(self) -> None:
        if self._seed is None:
            return
        sx, sy = self._seed
        self._mask = build_mask(
            self._arr, sx, sy, self._tolerance.value(), self._grow.value(),
        )
        self._render_preview()

    def _render_preview(self) -> None:
        rgb = self._arr[..., :_RGB_STRIDE].astype(np.float32)
        if self._mask is not None and self._mask.any():
            blended = rgb[self._mask] * (1.0 - _OVERLAY_ALPHA) + _OVERLAY_RGB * _OVERLAY_ALPHA
            rgb = rgb.copy()
            rgb[self._mask] = blended
        disp = np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))
        height, width = disp.shape[:2]
        image = QImage(disp.data, width, height, _RGB_STRIDE * width,
                       QImage.Format.Format_RGB888).copy()
        self._preview.setPixmap(QPixmap.fromImage(image).scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    # -- apply --------------------------------------------------------------

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._mask is None or not self._mask.any() or self._worker is not None:
            self._notify("object_remove_no_selection", "Click the object first")
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_edited.png")
        self._worker = _RemoveWorker(
            self._arr, self._mask, str(out_path), self._method.currentData(),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        if not ok:
            self._notify("object_remove_failed", "Object removal failed", message)
            return
        lang = language_wrapper.language_word_dict
        self._toast(lang.get("object_remove_done", "Saved {path}").format(
            path=Path(message).name), error=False)
        self.accept()

    def _notify(self, key: str, fallback: str, detail: str = "") -> None:  # pragma: no cover - Qt UI
        text = language_wrapper.language_word_dict.get(key, fallback)
        self._toast(f"{text}: {detail}" if detail else text, error=True)

    def _toast(self, text: str, error: bool) -> None:  # pragma: no cover - Qt UI
        main_window = getattr(self._viewer, "main_window", None)
        toast = getattr(main_window, "toast", None)
        if toast is not None:
            (toast.error if error else toast.info)(text)


class _RemoveWorker(QThread):
    """Run diffusion inpainting off the UI thread and save the result."""

    done = Signal(bool, str)

    def __init__(self, arr: np.ndarray, mask: np.ndarray, out_path: str,
                 model_path: str | None = None):
        super().__init__()
        self._arr = arr
        self._mask = mask
        self._out_path = out_path
        self._model_path = model_path

    def run(self) -> None:  # pragma: no cover - background thread
        try:
            if self._model_path:
                result = onnx_inpaint(self._arr, self._mask, self._model_path)
            else:
                result = remove_object(self._arr, self._mask)
            Image.fromarray(result, mode="RGBA").save(self._out_path)
        except (ImportError, OSError, ValueError) as exc:
            self.done.emit(False, str(exc))
            return
        self.done.emit(True, self._out_path)


class _SamMaskWorker(QThread):
    """Compute a SAM point-prompt mask off the UI thread (encoder is heavy)."""

    done = Signal(bool, object)

    def __init__(self, arr: np.ndarray, coord: tuple[int, int],
                 encoder: str, decoder: str):
        super().__init__()
        self._arr = arr
        self._coord = coord
        self._encoder = encoder
        self._decoder = decoder

    def run(self) -> None:  # pragma: no cover - background thread
        try:
            mask = sam_mask(self._arr, [self._coord], [1], self._encoder, self._decoder)
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            self.done.emit(False, str(exc))
            return
        self.done.emit(True, mask)


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "object_remove_title": "Remove Object",
        "object_remove_hint": "Click the object to select it, adjust tolerance, then Apply.",
        "object_remove_tolerance": "Tolerance:",
        "object_remove_grow": "Grow edge:",
        "object_remove_apply": "Apply",
        "object_remove_method": "Method:",
        "object_remove_method_diffusion": "Diffusion (fast)",
        "object_remove_selection": "Selection:",
        "object_remove_selection_flood": "Flood-fill (fast)",
        "object_remove_selection_sam": "SAM (precise)",
        "object_remove_models_hint": "Drop LaMa/ONNX inpaint models into plugins/ai_object_remove/models/.",
        "object_remove_done": "Saved {path}",
        "object_remove_failed": "Object removal failed",
        "object_remove_no_selection": "Click the object first",
    },
    "Traditional_Chinese": {
        "object_remove_title": "移除物件",
        "object_remove_hint": "點選要移除的物件，調整容差後按套用。",
        "object_remove_tolerance": "容差：",
        "object_remove_grow": "邊緣擴張：",
        "object_remove_apply": "套用",
        "object_remove_method": "方法：",
        "object_remove_method_diffusion": "擴散（快速）",
        "object_remove_selection": "選取方式：",
        "object_remove_selection_flood": "洪水填充（快速）",
        "object_remove_selection_sam": "SAM（精準）",
        "object_remove_models_hint": "將 LaMa/ONNX 修補模型放入 plugins/ai_object_remove/models/。",
        "object_remove_done": "已儲存 {path}",
        "object_remove_failed": "物件移除失敗",
        "object_remove_no_selection": "請先點選物件",
    },
    "Chinese": {
        "object_remove_title": "移除对象",
        "object_remove_hint": "点击要移除的对象，调整容差后点应用。",
        "object_remove_tolerance": "容差：",
        "object_remove_grow": "边缘扩张：",
        "object_remove_apply": "应用",
        "object_remove_method": "方法：",
        "object_remove_method_diffusion": "扩散（快速）",
        "object_remove_selection": "选取方式：",
        "object_remove_selection_flood": "洪水填充（快速）",
        "object_remove_selection_sam": "SAM（精准）",
        "object_remove_models_hint": "将 LaMa/ONNX 修补模型放入 plugins/ai_object_remove/models/。",
        "object_remove_done": "已保存 {path}",
        "object_remove_failed": "对象移除失败",
        "object_remove_no_selection": "请先点击对象",
    },
    "Japanese": {
        "object_remove_title": "オブジェクト除去",
        "object_remove_hint": "除去するオブジェクトをクリックし、許容値を調整して適用してください。",
        "object_remove_tolerance": "許容値:",
        "object_remove_grow": "エッジ拡張:",
        "object_remove_apply": "適用",
        "object_remove_method": "方式:",
        "object_remove_method_diffusion": "拡散（高速）",
        "object_remove_selection": "選択方法:",
        "object_remove_selection_flood": "塗りつぶし（高速）",
        "object_remove_selection_sam": "SAM（高精度）",
        "object_remove_models_hint": "LaMa/ONNX インペイントモデルを plugins/ai_object_remove/models/ に配置してください。",
        "object_remove_done": "保存しました: {path}",
        "object_remove_failed": "オブジェクト除去に失敗しました",
        "object_remove_no_selection": "先にオブジェクトをクリックしてください",
    },
    "Korean": {
        "object_remove_title": "개체 제거",
        "object_remove_hint": "제거할 개체를 클릭하고 허용값을 조정한 후 적용하세요.",
        "object_remove_tolerance": "허용값:",
        "object_remove_grow": "가장자리 확장:",
        "object_remove_apply": "적용",
        "object_remove_method": "방법:",
        "object_remove_method_diffusion": "확산(빠름)",
        "object_remove_selection": "선택 방법:",
        "object_remove_selection_flood": "플러드 필(빠름)",
        "object_remove_selection_sam": "SAM(정밀)",
        "object_remove_models_hint": "LaMa/ONNX 인페인트 모델을 plugins/ai_object_remove/models/에 넣으세요.",
        "object_remove_done": "{path}에 저장됨",
        "object_remove_failed": "개체 제거 실패",
        "object_remove_no_selection": "먼저 개체를 클릭하세요",
    },
}
