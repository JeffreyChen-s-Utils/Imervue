"""Layer dock edit handlers: row selection, inline rename/visibility, opacity, blend, alpha lock."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from Imervue.paint.docks._helpers import _strip_color_chip


class LayerEditHandlersMixin:
    """Slots that write a ``LayerDock`` control change back to the document."""

    def _on_search_changed(self, text: str) -> None:  # pragma: no cover - Qt UI
        self._search_query = text
        self.refresh()

    def _on_row_changed(self, row: int) -> None:
        if self._suspend or self._document is None or row < 0:
            return
        layer_idx = self._row_to_layer_index(row)
        if 0 <= layer_idx < self._document.layer_count:
            self._document.set_active_layer(layer_idx)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._suspend or self._document is None:
            return
        layer_idx = int(item.data(Qt.ItemDataRole.UserRole))
        new_visible = item.checkState() == Qt.CheckState.Checked
        # Editing the row inline writes back the displayed text — strip
        # the colour-chip glyph prefix (added by ``_label_with_color_chip``)
        # so the persisted layer name doesn't accumulate emoji.
        new_name = _strip_color_chip(item.text())
        layer = self._document.layer_at(layer_idx)
        if layer.name == new_name and layer.visible == new_visible:
            return
        self._document.set_layer_attribute(
            layer_idx, visible=new_visible, name=new_name,
        )
        self.edit_committed.emit()

    def _on_opacity_changed(self, value: int) -> None:
        if self._suspend or self._document is None:
            return
        active_idx = self._document.active_layer_index()
        if active_idx < 0:
            return
        # Compared as the slider's whole percentage: 0.07 * 100 is 7.000000000000001.
        if round(self._document.active_layer().opacity * 100) != value:
            self._document.set_layer_attribute(active_idx, opacity=value / 100.0)
            self.edit_committed.emit()

    def _on_blend_changed(self) -> None:
        if self._suspend or self._document is None:
            return
        active_idx = self._document.active_layer_index()
        if (active_idx >= 0
                and self._document.active_layer().blend_mode != self._blend.currentData()):
            self._document.set_layer_attribute(
                active_idx, blend_mode=self._blend.currentData(),
            )
            self.edit_committed.emit()

    def _on_lock_alpha_toggled(self, checked: bool) -> None:
        if self._suspend or self._document is None:
            return
        active_idx = self._document.active_layer_index()
        if (active_idx >= 0
                and self._document.set_layer_lock_alpha(active_idx, lock_alpha=checked)):
            self.edit_committed.emit()
