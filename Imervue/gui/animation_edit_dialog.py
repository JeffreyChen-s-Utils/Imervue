"""Animation-edit dialog — reverse / boomerang / speed / optimize a GIF.

Pure frame-list logic in :mod:`Imervue.image.animation_edit`; this is the Qt
shell (operation picker + speed slider, background worker).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QSlider, QVBoxLayout, QWidget

from Imervue.gui._apply_save import apply_save_buttons, current_image_path, notify_saved
from Imervue.image.animation_edit import OPERATIONS, edit_animation
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.animation_edit_dialog")

_SPEED_SCALE = 100.0


class _AnimationWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, operation: str, speed: float, out_path: str):
        super().__init__()
        self._path = path
        self._operation = operation
        self._speed = speed
        self._out = out_path

    def run(self) -> None:
        try:
            edit_animation(self._path, self._operation, self._out, speed=self._speed)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Animation edit failed: %s", exc)
            self.done.emit(False, str(exc))


class AnimationEditDialog(QDialog):
    """Operation + speed applied to the current animated image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _AnimationWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("animedit_title", "Edit Animation"))
        self.setMinimumWidth(360)

        self._operation = QComboBox()
        for op in OPERATIONS:
            self._operation.addItem(lang.get(f"animedit_{op}", op.title()), op)
        self._speed = QSlider(Qt.Orientation.Horizontal)
        self._speed.setRange(25, 400)   # 0.25x .. 4.0x
        self._speed.setValue(100)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("animedit_operation", "Operation:")))
        layout.addWidget(self._operation)
        layout.addWidget(QLabel(lang.get("animedit_speed_label", "Speed (× for Speed op):")))
        layout.addWidget(self._speed)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_edited.gif")
        self._worker = _AnimationWorker(
            self._path, self._operation.currentData(),
            self._speed.value() / _SPEED_SCALE, str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "animedit_failed", "Animation edit failed")
        if ok:
            self.accept()


def open_animation_edit(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        AnimationEditDialog(viewer, path).exec()
