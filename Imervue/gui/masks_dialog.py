"""Local adjustment masks dialog.

Lets the user build a list of brush / radial / linear masks with per-mask
adjustments. Masks are stored on ``Recipe.extra['masks']`` as a list of
serialised dicts so they round-trip through ``recipe_store``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.masks import (
    Mask,
    MaskAdjustments,
    masks_from_dict_list,
    masks_to_dict_list,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import get_for_path, set_for_path
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.masks_dialog")

_MASK_TYPES = ("brush", "radial", "linear")


class MasksDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("masks_title", "Local Adjustment Masks"))
        self.setMinimumWidth(520)

        self._masks: list[Mask] = self._load_existing()
        self._active_idx: int | None = None

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        self._refresh_list()

        add_brush = QPushButton(lang.get("masks_add_brush", "+ Brush"))
        add_brush.clicked.connect(lambda: self._add_mask("brush"))
        add_radial = QPushButton(lang.get("masks_add_radial", "+ Radial"))
        add_radial.clicked.connect(lambda: self._add_mask("radial"))
        add_linear = QPushButton(lang.get("masks_add_linear", "+ Linear"))
        add_linear.clicked.connect(lambda: self._add_mask("linear"))
        remove_btn = QPushButton(lang.get("masks_remove", "Remove"))
        remove_btn.clicked.connect(self._remove)
        add_row = QHBoxLayout()
        for b in (add_brush, add_radial, add_linear, remove_btn):
            add_row.addWidget(b)

        self._adj_group = QGroupBox(lang.get("masks_adjustments", "Adjustments"))
        self._build_adjustment_form(self._adj_group)
        self._adj_group.setEnabled(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("masks_list", "Masks:")))
        layout.addWidget(self._list)
        layout.addLayout(add_row)
        layout.addWidget(self._adj_group, 1)
        layout.addWidget(buttons)

    def _load_existing(self) -> list[Mask]:
        recipe = get_for_path(self._path) or Recipe()
        return masks_from_dict_list(recipe.extra.get("masks") or [])

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for i, m in enumerate(self._masks):
            self._list.addItem(f"{i + 1}. {m.mask_type}")
        self._list.blockSignals(False)

    def _build_adjustment_form(self, group: QGroupBox) -> None:
        self._exposure = self._spin(-2.0, 2.0, 0.1)
        self._brightness = self._spin(-1.0, 1.0, 0.05)
        self._contrast = self._spin(-1.0, 1.0, 0.05)
        self._saturation = self._spin(-1.0, 1.0, 0.05)
        self._temperature = self._spin(-1.0, 1.0, 0.05)
        self._tint = self._spin(-1.0, 1.0, 0.05)
        self._feather = self._spin(0.0, 1.0, 0.05, value=0.5)
        for s in (self._exposure, self._brightness, self._contrast,
                  self._saturation, self._temperature, self._tint,
                  self._feather):
            s.valueChanged.connect(self._on_adjust_change)

        lang = language_wrapper.language_word_dict
        form = QFormLayout(group)
        form.addRow(lang.get("masks_exposure", "Exposure:"), self._exposure)
        form.addRow(lang.get("masks_brightness", "Brightness:"), self._brightness)
        form.addRow(lang.get("masks_contrast", "Contrast:"), self._contrast)
        form.addRow(lang.get("masks_saturation", "Saturation:"), self._saturation)
        form.addRow(lang.get("masks_temperature", "Temperature:"), self._temperature)
        form.addRow(lang.get("masks_tint", "Tint:"), self._tint)
        form.addRow(lang.get("masks_feather", "Feather:"), self._feather)

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float,
              value: float = 0.0) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(minimum, maximum)
        s.setSingleStep(step)
        s.setDecimals(3)
        s.setValue(value)
        return s

    def _add_mask(self, mask_type: str) -> None:
        if mask_type not in _MASK_TYPES:
            return
        # Default params use image centre — users tweak via numeric fields
        # once we expose them; for now the defaults cover the centre region.
        params = self._default_params_for(mask_type)
        self._masks.append(Mask(mask_type=mask_type, params=params))
        self._refresh_list()
        self._list.setCurrentRow(len(self._masks) - 1)

    def _default_params_for(self, mask_type: str) -> dict:
        viewer = self._viewer
        model = getattr(viewer, "model", None)
        cur = getattr(model, "current_image", None) if model else None
        width = int(getattr(cur, "width", 0) or 0) or 1000
        height = int(getattr(cur, "height", 0) or 0) or 1000
        if mask_type == "brush":
            return {"points": [{"x": width / 2.0, "y": height / 2.0,
                                "r": min(width, height) / 6.0}]}
        if mask_type == "radial":
            return {"cx": width / 2.0, "cy": height / 2.0,
                    "rx": width / 4.0, "ry": height / 4.0}
        return {"x0": 0.0, "y0": height / 2.0,
                "x1": float(width), "y1": height / 2.0}

    def _remove(self) -> None:
        idx = self._list.currentRow()
        if idx < 0 or idx >= len(self._masks):
            return
        del self._masks[idx]
        self._refresh_list()
        self._adj_group.setEnabled(False)

    def _on_select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._masks):
            self._adj_group.setEnabled(False)
            self._active_idx = None
            return
        self._active_idx = idx
        m = self._masks[idx]
        self._adj_group.setEnabled(True)
        for spin, value in (
            (self._exposure, m.adjustments.exposure),
            (self._brightness, m.adjustments.brightness),
            (self._contrast, m.adjustments.contrast),
            (self._saturation, m.adjustments.saturation),
            (self._temperature, m.adjustments.temperature),
            (self._tint, m.adjustments.tint),
            (self._feather, m.feather),
        ):
            spin.blockSignals(True)
            spin.setValue(float(value))
            spin.blockSignals(False)

    def _on_adjust_change(self, _v: float) -> None:
        if self._active_idx is None:
            return
        m = self._masks[self._active_idx]
        m.adjustments = MaskAdjustments(
            exposure=self._exposure.value(),
            brightness=self._brightness.value(),
            contrast=self._contrast.value(),
            saturation=self._saturation.value(),
            temperature=self._temperature.value(),
            tint=self._tint.value(),
        )
        m.feather = self._feather.value()

    def _save(self) -> None:
        recipe = get_for_path(self._path) or Recipe()
        recipe.extra["masks"] = masks_to_dict_list(self._masks)
        set_for_path(self._path, recipe)
        reload_fn = getattr(self._viewer, "reload_current_image", None)
        if callable(reload_fn):
            reload_fn()
        self.accept()


def open_masks(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    MasksDialog(viewer, str(path)).exec()
