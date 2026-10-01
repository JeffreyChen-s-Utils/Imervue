"""AI Outpaint plugin — extend the current image's canvas and fill the border.

Pure expansion + diffusion fill live in :mod:`ai_outpaint.outpaint`; this is the
Qt shell (menu entry, padding dialog, background worker).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
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
from Imervue.plugin.tool_dialog import ToolDialogMixin, Transform

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_DEFAULT_PAD = 64
_SLIDER_MAX = 512


class AIOutpaintPlugin(ImervuePlugin):
    plugin_name = "AI Outpaint"
    plugin_version = "1.0.1"
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


class OutpaintDialog(ToolDialogMixin, QDialog):
    """Pick a border width and outpaint the current image on Apply."""

    output_suffix = "outpaint"
    failed_key = "outpaint_failed"
    failed_text = "Outpaint failed"
    done_key = "outpaint_done"

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
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

    def _transform(self) -> Transform:
        padding = self._padding.value()
        return lambda rgba: outpaint(rgba, padding)


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
