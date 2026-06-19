"""AI Outpaint plugin — extend the current image's canvas and fill the border.

Pure expansion + diffusion fill live in :mod:`ai_outpaint.outpaint`; this is the
Qt shell (menu entry, padding dialog, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ai_outpaint.outpaint import outpaint
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_outpaint")

_DEFAULT_PAD = 64
_SLIDER_MAX = 512


class AIOutpaintPlugin(ImervuePlugin):
    plugin_name = "AI Outpaint"
    plugin_version = "1.0.0"
    plugin_description = "Extend an image's canvas and fill the new border."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return _TRANSLATIONS

    def on_build_menu_bar(self, plugin_menu) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        action = plugin_menu.addAction(lang.get("outpaint_title", "Outpaint…"))
        action.triggered.connect(self._open_dialog)

    def _open_dialog(self) -> None:  # pragma: no cover - Qt UI
        viewer = getattr(self, "viewer", None)
        images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
        idx = getattr(viewer, "current_index", -1)
        if 0 <= idx < len(images):
            OutpaintDialog(viewer, str(images[idx])).exec()


class OutpaintDialog(QDialog):
    """Pick a border width and outpaint the current image on Apply."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _OutpaintWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("outpaint_title", "Outpaint…"))
        self.setMinimumWidth(360)

        self._padding = QSlider(Qt.Orientation.Horizontal)
        self._padding.setRange(0, _SLIDER_MAX)
        self._padding.setValue(_DEFAULT_PAD)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("outpaint_padding", "Border (px):")))
        layout.addWidget(self._padding)
        layout.addLayout(self._build_buttons(lang))

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton(lang.get("outpaint_apply", "Apply"))
        apply_btn.clicked.connect(self._commit)
        row.addWidget(cancel)
        row.addWidget(apply_btn)
        return row

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_outpaint.png")
        self._worker = _OutpaintWorker(self._path, self._padding.value(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        lang = language_wrapper.language_word_dict
        toast = getattr(getattr(self._viewer, "main_window", None), "toast", None)
        if toast is not None:
            if ok:
                toast.info(lang.get("outpaint_done", "Saved {path}").format(
                    path=Path(message).name))
            else:
                toast.error(f"{lang.get('outpaint_failed', 'Outpaint failed')}: {message}")
        if ok:
            self.accept()


class _OutpaintWorker(QThread):
    """Run outpaint off the UI thread and save the result."""

    done = Signal(bool, str)

    def __init__(self, path: str, padding: int, out_path: str):
        super().__init__()
        self._path = path
        self._padding = padding
        self._out_path = out_path

    def run(self) -> None:  # pragma: no cover - background thread
        try:
            result = outpaint(_load_rgba(self._path), self._padding)
            Image.fromarray(result, mode="RGBA").save(self._out_path)
        except (OSError, ValueError) as exc:
            self.done.emit(False, str(exc))
            return
        self.done.emit(True, self._out_path)


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "outpaint_title": "Outpaint…",
        "outpaint_padding": "Border (px):",
        "outpaint_apply": "Apply",
        "outpaint_done": "Saved {path}",
        "outpaint_failed": "Outpaint failed",
    },
    "Traditional_Chinese": {
        "outpaint_title": "向外延展…",
        "outpaint_padding": "邊框（像素）：",
        "outpaint_apply": "套用",
        "outpaint_done": "已儲存 {path}",
        "outpaint_failed": "外擴失敗",
    },
    "Chinese": {
        "outpaint_title": "向外扩展…",
        "outpaint_padding": "边框（像素）：",
        "outpaint_apply": "应用",
        "outpaint_done": "已保存 {path}",
        "outpaint_failed": "外扩失败",
    },
    "Japanese": {
        "outpaint_title": "アウトペイント…",
        "outpaint_padding": "余白（px）:",
        "outpaint_apply": "適用",
        "outpaint_done": "保存しました: {path}",
        "outpaint_failed": "アウトペイント失敗",
    },
    "Korean": {
        "outpaint_title": "아웃페인트…",
        "outpaint_padding": "테두리(px):",
        "outpaint_apply": "적용",
        "outpaint_done": "{path} 저장됨",
        "outpaint_failed": "아웃페인트 실패",
    },
}
