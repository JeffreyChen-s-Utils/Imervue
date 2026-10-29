"""Layer dock stack actions: add / remove / duplicate / move and adjustment layers."""
from __future__ import annotations

from PySide6.QtWidgets import QMenu

from Imervue.multi_language.language_wrapper import language_wrapper


class LayerStackActionsMixin:
    """Buttons and popup entries that change the layer stack of a ``LayerDock``."""

    def _on_add(self) -> None:
        if self._document is None or self._document.layer_count == 0:
            return
        self._document.add_layer()
        self.edit_committed.emit()

    def _build_adjustment_menu(self) -> QMenu:
        """Build the Adjustment-Layer popup menu lazily.

        Each entry adds a fresh layer with the matching ``Adjustment``
        instance pre-installed using the catalogue's documented
        defaults — the user can then tweak the parameters in the
        Adjustments dialog without first having to pick a kind.
        """
        from Imervue.paint.adjustments import (
            ADJUSTMENT_KINDS,
            DEFAULT_PARAMS,
        )
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        for kind in ADJUSTMENT_KINDS:
            label = lang.get(
                f"paint_adjustment_{kind}",
                kind.replace("_", " ").title(),
            )
            action = menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, k=kind: self._add_adjustment_layer(
                    k, dict(DEFAULT_PARAMS.get(k, {})),
                ),
            )
        return menu

    def _add_adjustment_layer(self, kind: str, params: dict) -> None:
        from Imervue.paint.adjustments import Adjustment
        if self._document is None or self._document.layer_count == 0:
            return
        layer = self._document.add_layer()
        layer.adjustment = Adjustment(kind=kind, params=params)
        layer.name = self._unique_adjustment_name(kind)
        self._document.invalidate_composite()
        self.refresh()
        self.edit_committed.emit()

    def _unique_adjustment_name(self, kind: str) -> str:
        """Return ``"<Kind> 1"`` (or 2/3/...) so successive adjustment
        layers of the same kind get sortable, non-clashing names."""
        prefix = kind.replace("_", " ").title()
        if self._document is None:
            return prefix
        existing = {layer.name for layer in self._document.layers()}
        i = 1
        while True:
            candidate = f"{prefix} {i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _on_remove(self) -> None:
        if self._document is None or self._document.layer_count <= 1:
            return
        self._document.remove_active_layer()
        self.edit_committed.emit()

    def _on_duplicate(self) -> None:
        if self._document is None or self._document.active_layer() is None:
            return
        self._document.duplicate_active_layer()
        self.edit_committed.emit()

    def _on_move(self, *, up: bool) -> None:
        if self._document is None:
            return
        before = self._document.active_layer_index()
        self._document.move_active_layer(up=up)
        if self._document.active_layer_index() != before:
            self.edit_committed.emit()
