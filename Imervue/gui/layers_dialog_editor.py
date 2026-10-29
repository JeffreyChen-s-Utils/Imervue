"""Editor-to-model handlers and kind-specific pickers for the layers dialog."""
from __future__ import annotations

from PySide6.QtWidgets import QColorDialog, QFileDialog

from Imervue.gui.file_filters import image_filter
from Imervue.gui.layers_dialog_model import _default_params, _describe_layer
from Imervue.image.layers import Layer
from Imervue.multi_language.language_wrapper import language_wrapper


class LayersEditorMixin:
    """Write form edits back to the selected layer and refresh its list row."""

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
            image_filter(("png", "jpg", "jpeg", "webp", "bmp", "tiff")),
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
