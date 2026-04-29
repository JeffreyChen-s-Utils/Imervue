"""Manager dialog for the recipe's overlay layer stack.

Provides a list-based editor over ``recipe.extra['layers']``: add / remove
/ reorder layers, edit per-layer kind (text / image / lut), opacity, blend
mode, and kind-specific parameters. The dialog hands the modified recipe
back to the caller via ``accepted`` so the caller decides how to commit
(usually through ``recipe_store.set`` and a deep-zoom reload).

Pure-data helpers (``move_layer_up``, ``move_layer_down``) are split out
so they can be unit-tested without instantiating Qt.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.layers import (
    BLEND_MODES,
    DEFAULT_OPACITY,
    LAYER_KINDS,
    MAX_LAYERS,
    Layer,
    layers_from_dict_list,
    layers_to_dict_list,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe

logger = logging.getLogger("Imervue.layers_dialog")


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def move_layer_up(layers: list[Layer], idx: int) -> int:
    """Swap ``layers[idx]`` with ``layers[idx-1]``. Returns the new index."""
    if idx <= 0 or idx >= len(layers):
        return idx
    layers[idx - 1], layers[idx] = layers[idx], layers[idx - 1]
    return idx - 1


def move_layer_down(layers: list[Layer], idx: int) -> int:
    """Swap ``layers[idx]`` with ``layers[idx+1]``. Returns the new index."""
    if idx < 0 or idx >= len(layers) - 1:
        return idx
    layers[idx + 1], layers[idx] = layers[idx], layers[idx + 1]
    return idx + 1


def add_default_layer(layers: list[Layer], kind: str = "text") -> Layer | None:
    """Append a default-configured layer of ``kind``. Respects MAX_LAYERS."""
    if len(layers) >= MAX_LAYERS:
        return None
    if kind not in LAYER_KINDS:
        kind = "text"
    layer = Layer(
        kind=kind,
        enabled=True,
        opacity=DEFAULT_OPACITY,
        blend_mode="normal",
        params=_default_params(kind),
    )
    layers.append(layer)
    return layer


def _default_params(kind: str) -> dict:
    if kind == "text":
        return {
            "text": "",
            "corner": "bottom-right",
            "color": [255, 255, 255],
            "font_fraction": 0.035,
            "shadow": True,
        }
    if kind == "image":
        return {"path": ""}
    if kind == "lut":
        return {"path": "", "intensity": 1.0}
    return {}


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class LayersDialog(QDialog):
    """Edit the layer stack stored on a recipe and emit the new layers."""

    layers_changed = Signal(list)  # list[dict] — serialised layers

    def __init__(self, recipe: Recipe, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("layers_title", "Layers"))
        self.setModal(True)
        self.resize(720, 460)

        raw = recipe.extra.get("layers") if recipe.extra else None
        self._layers: list[Layer] = layers_from_dict_list(raw or [])

        outer = QHBoxLayout(self)
        outer.addLayout(self._build_left_column(), stretch=1)
        outer.addWidget(self._build_editor_panel(), stretch=2)

        self._refresh_list()
        if self._layers:
            self._list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_left_column(self) -> QVBoxLayout:
        lang = language_wrapper.language_word_dict
        col = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        col.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton(lang.get("layers_add", "Add"))
        btn_add.clicked.connect(self._add_layer)
        btn_remove = QPushButton(lang.get("layers_remove", "Remove"))
        btn_remove.clicked.connect(self._remove_layer)
        btn_up = QPushButton(lang.get("layers_up", "↑"))
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton(lang.get("layers_down", "↓"))
        btn_down.clicked.connect(self._move_down)
        for b in (btn_add, btn_remove, btn_up, btn_down):
            btn_row.addWidget(b)
        col.addLayout(btn_row)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        btn_apply = QPushButton(lang.get("layers_apply", "Apply"))
        btn_apply.clicked.connect(self._apply)
        btn_close = QPushButton(lang.get("close", "Close"))
        btn_close.clicked.connect(self.reject)
        save_row.addWidget(btn_apply)
        save_row.addWidget(btn_close)
        col.addLayout(save_row)
        return col

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self._editor_stack = QStackedWidget()

        self._editor_empty = QLabel(
            language_wrapper.language_word_dict.get(
                "layers_select_hint", "Select or add a layer to edit it."
            )
        )
        self._editor_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._editor_stack.addWidget(self._editor_empty)        # idx 0

        self._editor_form = self._build_form()
        self._editor_stack.addWidget(self._editor_form)         # idx 1

        layout.addWidget(self._editor_stack)
        return panel

    def _build_form(self) -> QWidget:
        lang = language_wrapper.language_word_dict
        widget = QWidget()
        form = QFormLayout(widget)

        self._kind_combo = QComboBox()
        for k in LAYER_KINDS:
            self._kind_combo.addItem(
                lang.get(f"layers_kind_{k}", k.title()), userData=k,
            )
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)

        self._opacity_spin = QDoubleSpinBox()
        self._opacity_spin.setRange(0.0, 1.0)
        self._opacity_spin.setDecimals(2)
        self._opacity_spin.setSingleStep(0.05)
        self._opacity_spin.valueChanged.connect(self._on_opacity_changed)

        self._blend_combo = QComboBox()
        for m in BLEND_MODES:
            self._blend_combo.addItem(
                lang.get(f"layers_blend_{m}", m.title()), userData=m,
            )
        self._blend_combo.currentIndexChanged.connect(self._on_blend_changed)

        form.addRow(lang.get("layers_kind", "Kind:"), self._kind_combo)
        form.addRow(lang.get("layers_opacity", "Opacity:"), self._opacity_spin)
        form.addRow(lang.get("layers_blend", "Blend:"), self._blend_combo)

        # Kind-specific param row: a single line edit + Browse / Color button
        # which we re-wire whenever the active kind changes.
        self._param_row = QHBoxLayout()
        self._param_field = QLineEdit()
        self._param_field.editingFinished.connect(self._on_param_text_changed)
        self._param_button = QPushButton("…")
        self._param_button.clicked.connect(self._on_param_button_clicked)
        self._param_row.addWidget(self._param_field, stretch=1)
        self._param_row.addWidget(self._param_button)
        form.addRow(lang.get("layers_param", "Parameter:"), self._param_row)

        return widget

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        self._list.clear()
        for layer in self._layers:
            self._list.addItem(QListWidgetItem(_describe_layer(layer)))

    def _current_layer(self) -> Layer | None:
        idx = self._list.currentRow()
        if 0 <= idx < len(self._layers):
            return self._layers[idx]
        return None

    def _on_row_changed(self, _idx: int) -> None:
        layer = self._current_layer()
        if layer is None:
            self._editor_stack.setCurrentIndex(0)
            return
        self._editor_stack.setCurrentIndex(1)
        self._sync_form_from_layer(layer)

    def _sync_form_from_layer(self, layer: Layer) -> None:
        for combo, value in (
            (self._kind_combo, layer.kind),
            (self._blend_combo, layer.blend_mode),
        ):
            combo.blockSignals(True)
            for i in range(combo.count()):
                if combo.itemData(i) == value:
                    combo.setCurrentIndex(i)
                    break
            combo.blockSignals(False)
        self._opacity_spin.blockSignals(True)
        self._opacity_spin.setValue(float(layer.opacity))
        self._opacity_spin.blockSignals(False)
        self._sync_param_from_layer(layer)

    def _sync_param_from_layer(self, layer: Layer) -> None:
        self._param_field.blockSignals(True)
        if layer.kind == "text":
            self._param_field.setText(str(layer.params.get("text", "")))
            self._param_button.setText(
                language_wrapper.language_word_dict.get(
                    "layers_color", "Color"
                )
            )
        elif layer.kind in ("image", "lut"):
            self._param_field.setText(str(layer.params.get("path", "")))
            self._param_button.setText(
                language_wrapper.language_word_dict.get(
                    "layers_browse", "Browse…"
                )
            )
        else:
            self._param_field.setText("")
            self._param_button.setText("…")
        self._param_field.blockSignals(False)

    # ------------------------------------------------------------------
    # Editor → model
    # ------------------------------------------------------------------

    def _on_kind_changed(self, _idx: int) -> None:
        layer = self._current_layer()
        if layer is None:
            return
        new_kind = self._kind_combo.currentData()
        if new_kind == layer.kind:
            return
        layer.kind = new_kind
        layer.params = _default_params(new_kind)
        self._sync_param_from_layer(layer)
        self._refresh_current_row_label()

    def _on_opacity_changed(self, value: float) -> None:
        layer = self._current_layer()
        if layer is not None:
            layer.opacity = float(value)
            self._refresh_current_row_label()

    def _on_blend_changed(self, _idx: int) -> None:
        layer = self._current_layer()
        if layer is None:
            return
        layer.blend_mode = self._blend_combo.currentData()
        self._refresh_current_row_label()

    def _on_param_text_changed(self) -> None:
        layer = self._current_layer()
        if layer is None:
            return
        text = self._param_field.text()
        if layer.kind == "text":
            layer.params["text"] = text
        elif layer.kind in ("image", "lut"):
            layer.params["path"] = text
        self._refresh_current_row_label()

    def _on_param_button_clicked(self) -> None:
        layer = self._current_layer()
        if layer is None:
            return
        if layer.kind == "text":
            self._pick_color_for(layer)
        elif layer.kind == "image":
            self._pick_image_path_for(layer)
        elif layer.kind == "lut":
            self._pick_lut_path_for(layer)

    def _pick_color_for(self, layer: Layer) -> None:
        current = layer.params.get("color") or [255, 255, 255]
        from PySide6.QtGui import QColor
        initial = QColor(int(current[0]), int(current[1]), int(current[2]))
        chosen = QColorDialog.getColor(initial, self)
        if chosen.isValid():
            layer.params["color"] = [chosen.red(), chosen.green(), chosen.blue()]

    def _pick_image_path_for(self, layer: Layer) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            language_wrapper.language_word_dict.get("layers_pick_image", "Choose image"),
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
        )
        if path:
            layer.params["path"] = path
            self._param_field.setText(path)
            self._refresh_current_row_label()

    def _pick_lut_path_for(self, layer: Layer) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            language_wrapper.language_word_dict.get("layers_pick_lut", "Choose LUT"),
            "",
            "Cube LUT (*.cube)",
        )
        if path:
            layer.params["path"] = path
            self._param_field.setText(path)
            self._refresh_current_row_label()

    def _refresh_current_row_label(self) -> None:
        idx = self._list.currentRow()
        layer = self._current_layer()
        if layer is None or idx < 0:
            return
        item = self._list.item(idx)
        if item is not None:
            item.setText(_describe_layer(layer))

    # ------------------------------------------------------------------
    # Add / remove / reorder
    # ------------------------------------------------------------------

    def _add_layer(self) -> None:
        if add_default_layer(self._layers, kind="text") is None:
            return
        self._refresh_list()
        self._list.setCurrentRow(len(self._layers) - 1)

    def _remove_layer(self) -> None:
        idx = self._list.currentRow()
        if 0 <= idx < len(self._layers):
            self._layers.pop(idx)
            self._refresh_list()
            new_row = min(idx, len(self._layers) - 1)
            if new_row >= 0:
                self._list.setCurrentRow(new_row)

    def _move_up(self) -> None:
        idx = self._list.currentRow()
        new_idx = move_layer_up(self._layers, idx)
        if new_idx != idx:
            self._refresh_list()
            self._list.setCurrentRow(new_idx)

    def _move_down(self) -> None:
        idx = self._list.currentRow()
        new_idx = move_layer_down(self._layers, idx)
        if new_idx != idx:
            self._refresh_list()
            self._list.setCurrentRow(new_idx)

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _apply(self) -> None:
        self.layers_changed.emit(layers_to_dict_list(self._layers))
        self.accept()


def _describe_layer(layer: Layer) -> str:
    """Human-readable one-line summary for the list row."""
    suffix = ""
    if layer.kind == "text":
        suffix = layer.params.get("text", "") or "(empty)"
    elif layer.kind in ("image", "lut"):
        path = layer.params.get("path", "") or "(none)"
        # Show only the filename to keep the row narrow
        suffix = path.replace("\\", "/").rsplit("/", 1)[-1] or path
    enabled_marker = "" if layer.enabled else " [off]"
    return (
        f"{layer.kind.title()} • {layer.blend_mode} • "
        f"{int(layer.opacity * 100)}% — {suffix}{enabled_marker}"
    )


def open_layers_dialog(recipe: Recipe, parent=None):
    """Open the dialog and return the new layer-dicts list, or None if cancelled."""
    dlg = LayersDialog(recipe, parent=parent)
    captured: dict = {}
    dlg.layers_changed.connect(lambda lst: captured.update(value=lst))
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return captured.get("value")
    return None
