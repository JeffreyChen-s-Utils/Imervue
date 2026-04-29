"""Portrait mode plugin — fakes shallow depth-of-field via rembg + blur.

The compositing pipeline lives in ``Imervue.image.portrait_blur``; this
module wraps rembg to extract a subject mask, then hands both arrays
off. ``rembg`` and ``onnxruntime`` are optional — the plugin reports a
graceful failure when they're not installed.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from portrait_mode.portrait_blur import (
    BLUR_RADIUS_MAX,
    BLUR_RADIUS_MIN,
    FEATHER_RADIUS_MAX,
    FEATHER_RADIUS_MIN,
    PortraitBlurOptions,
    apply_portrait_blur,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.portrait_mode")


class PortraitModePlugin(ImervuePlugin):
    plugin_name = "Portrait Mode"
    plugin_version = "1.0.0"
    plugin_description = "Subject-isolated background blur via rembg."
    plugin_author = "Imervue"

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
                            lang.get("portrait_mode_title", "Portrait Mode"),
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
        PortraitModeDialog(viewer, str(images[idx])).exec()


class PortraitModeDialog(QDialog):
    """Slider-driven blur + feather options. Runs synchronously on OK."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("portrait_mode_title", "Portrait Mode"))
        self.setMinimumWidth(420)

        self._blur = QSpinBox()
        self._blur.setRange(BLUR_RADIUS_MIN, BLUR_RADIUS_MAX)
        self._blur.setValue(16)

        self._feather = QSpinBox()
        self._feather.setRange(FEATHER_RADIUS_MIN, FEATHER_RADIUS_MAX)
        self._feather.setValue(4)

        hint = QLabel(
            lang.get(
                "portrait_mode_hint",
                "Writes <name>_portrait.png next to the source. "
                "Requires rembg + onnxruntime.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("portrait_mode_blur", "Blur radius:"), self._blur)
        form.addRow(lang.get("portrait_mode_feather", "Feather radius:"),
                    self._feather)
        return form

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
            mask = _extract_subject_mask(arr)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            self._notify_failure(exc)
            return

        options = PortraitBlurOptions(
            blur_radius=int(self._blur.value()),
            feather_radius=int(self._feather.value()),
        )
        try:
            composite = apply_portrait_blur(arr, mask, options)
        except ValueError as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_portrait.png",
        )
        try:
            Image.fromarray(composite, mode="RGBA").save(str(out_path))
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
                "portrait_mode_failed", "Portrait mode failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "portrait_mode_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def _extract_subject_mask(arr: np.ndarray) -> np.ndarray:
    """Run rembg on the input and return a uint8 (H, W) mask.

    rembg returns an RGBA image where the alpha channel IS the subject
    mask, so we just call ``remove`` and read alpha back. ``rembg`` and
    ``onnxruntime`` are optional dependencies; ImportError surfaces as a
    user-facing toast in the calling dialog.
    """
    try:
        from rembg import remove
    except ImportError as exc:
        raise ImportError(
            "rembg is required for Portrait Mode. Install via the plugin manager.",
        ) from exc
    img_pil = Image.fromarray(arr, mode="RGBA")
    cut_pil = remove(img_pil)
    cut_arr = np.array(cut_pil)
    if cut_arr.ndim != 3 or cut_arr.shape[2] != 4:
        raise RuntimeError("rembg returned an unexpected image shape")
    return cut_arr[..., 3]
