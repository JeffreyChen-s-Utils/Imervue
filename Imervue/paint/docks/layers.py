"""Layer dock."""
from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts

from Imervue.paint.docks._helpers import (
    _array_to_icon,
    _label_with_color_chip,
    _slider,
    _strip_color_chip,
)


class LayerDock(QDockWidget):
    """Layer list bound to a :class:`Imervue.paint.document.PaintDocument`.

    Reflects the document's stack, lets the user reorder / add / remove
    / toggle visibility, and edits the active layer's opacity and blend
    mode. The dock subscribes to the document's listener channel so
    external changes (e.g. a tool that adds a layer) refresh the
    visible state automatically.
    """

    def __init__(self, document=None, parent=None):
        from Imervue.paint.layer_thumbnail import (
            DEFAULT_THUMBNAIL_SIZE, ThumbnailCache,
        )
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_layers", "Layers"), parent)
        self._document = document
        self._suspend = False
        self._search_query = ""
        self._thumbnail_cache = ThumbnailCache()
        self._thumbnail_size = DEFAULT_THUMBNAIL_SIZE

        body = QWidget()
        layout = QVBoxLayout(body)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            lang.get("paint_layers_search", "Search layers…"),
        )
        self._search.setClearButtonEnabled(True)
        self._search.setToolTip(
            lang.get(
                "paint_layers_search_tooltip",
                "Filter the layer list by name — case-insensitive substring match",
            ),
        )
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setIconSize(
            QPixmap(self._thumbnail_size, self._thumbnail_size).size(),
        )
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_changed)
        # F2 enters inline rename on the active layer — the page dock
        # uses the same trigger pair so the muscle memory transfers.
        # Double-click stays free for layer-mask edit so we don't add
        # DoubleClicked here.
        from PySide6.QtWidgets import QAbstractItemView
        self._list.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked,
        )
        layout.addWidget(self._list, stretch=1)

        row = QHBoxLayout()
        # Tooltip text appends the keybind from the shortcut registry so
        # the affordance is discoverable: hovering "+" reveals
        # ``Add layer (Ctrl+Shift+N)`` rather than just the glyph.
        from Imervue.paint.shortcut_registry import load_shortcuts
        shortcuts = load_shortcuts()

        def _tooltip_with_shortcut(key: str, fallback: str, action_id: str) -> str:
            label = lang.get(key, fallback)
            try:
                hotkey = shortcuts.get(action_id)
            except KeyError:
                return label
            return f"{label} ({hotkey})" if hotkey else label

        for key, fallback, slot, tooltip_key, tooltip_fallback, action_id in (
            ("paint_layers_add", "+", self._on_add,
             "paint_layers_add_tooltip", "Add layer", "paint.layer.add"),
            ("paint_layers_remove", "−", self._on_remove,
             "paint_layers_remove_tooltip", "Delete layer", ""),
            ("paint_layers_up", "↑", lambda: self._on_move(up=True),
             "paint_layers_up_tooltip", "Move layer up", "paint.layer.move_up"),
            ("paint_layers_down", "↓", lambda: self._on_move(up=False),
             "paint_layers_down_tooltip", "Move layer down", "paint.layer.move_down"),
            ("paint_layers_duplicate", "⧉", self._on_duplicate,
             "paint_layers_duplicate_tooltip", "Duplicate layer",
             "paint.layer.duplicate"),
        ):
            btn = QToolButton()
            btn.setText(lang.get(key, fallback))
            btn.setToolTip(
                _tooltip_with_shortcut(tooltip_key, tooltip_fallback, action_id)
                if action_id else lang.get(tooltip_key, tooltip_fallback),
            )
            btn.clicked.connect(slot)
            row.addWidget(btn)
        # Dedicated "add adjustment layer" entry — raster paint apps's Layer
        # palette has the same affordance under a separate icon. The
        # ``+◐`` glyph (plus + half-tone disc) marks it as an
        # adjustment-only insert vs the plain ``+`` raster add.
        adj_btn = QToolButton()
        adj_btn.setText(
            lang.get("paint_layers_add_adjustment", "+◐"),
        )
        adj_btn.setToolTip(
            lang.get(
                "paint_layers_add_adjustment_tooltip",
                "Add adjustment layer…",
            ),
        )
        adj_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        adj_btn.setMenu(self._build_adjustment_menu())
        row.addWidget(adj_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # Per-layer locks — alpha lock is the most-requested affordance
        # (Photoshop's "Transparency" lock) so we surface it on the
        # active layer alongside opacity / blend rather than buried in
        # a context menu.
        lock_row = QHBoxLayout()
        self._lock_alpha_btn = QToolButton()
        self._lock_alpha_btn.setText(
            lang.get("paint_layers_lock_alpha", "🔒α"),
        )
        self._lock_alpha_btn.setCheckable(True)
        self._lock_alpha_btn.setToolTip(
            lang.get(
                "paint_layers_lock_alpha_tooltip",
                "Lock transparency — paint only where the active layer "
                "already has pixels (Photoshop ⊠ Transparency)",
            ),
        )
        self._lock_alpha_btn.toggled.connect(self._on_lock_alpha_toggled)
        lock_row.addWidget(self._lock_alpha_btn)
        lock_row.addStretch(1)
        layout.addLayout(lock_row)

        layout.addWidget(QLabel(lang.get("paint_layers_opacity", "Opacity:")))
        self._opacity = _slider(0, 100, 100)
        self._opacity.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self._opacity)

        layout.addWidget(QLabel(lang.get("paint_layers_blend", "Blend:")))
        self._blend = QComboBox()
        for mode in ts.BLEND_MODES:
            self._blend.addItem(
                lang.get(f"paint_blend_{mode}", mode.replace("_", " ").title()),
                userData=mode,
            )
        self._blend.currentIndexChanged.connect(self._on_blend_changed)
        layout.addWidget(self._blend)
        layout.addStretch(1)

        self.setWidget(body)

        if self._document is not None:
            self._unsubscribe = self._document.listen(self.refresh)
            self.destroyed.connect(lambda *_: self._unsubscribe())
            self.refresh()

    def set_document(self, document) -> None:
        if self._document is document:
            return
        self._document = document
        if document is None:
            self._list.clear()
            return
        self._unsubscribe = document.listen(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        if self._document is None:
            return
        self._suspend = True
        try:
            self._list.clear()
            visible_indices = self._filtered_indices()
            for idx, layer in enumerate(self._document.layers()):
                if idx not in visible_indices:
                    continue
                # Stack drawn top-down — most-recently-added layer at the
                # top of the visual list, matching raster paint apps / Photoshop.
                # The displayed row index ignores filtered-out rows so
                # the search produces a tight list rather than gappy.
                item = QListWidgetItem(_label_with_color_chip(layer))
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEditable,
                )
                item.setCheckState(
                    Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked,
                )
                item.setData(Qt.ItemDataRole.UserRole, idx)
                # Thumbnail — cached by content so a no-op refresh is
                # cheap. Falls back to a blank pixmap for an empty image.
                thumb_arr = self._thumbnail_cache.get(
                    layer.image, size=self._thumbnail_size,
                )
                item.setIcon(_array_to_icon(thumb_arr))
                # Insertion order = newest-first; we walk the stack
                # top-down by appending in reverse-active order. Use
                # insertItem(0, ...) so each new entry stacks on top.
                self._list.insertItem(0, item)
            active_idx = self._document.active_layer_index()
            if active_idx in visible_indices:
                # Find the dock-row position of the active layer.
                for row in range(self._list.count()):
                    item = self._list.item(row)
                    if item.data(Qt.ItemDataRole.UserRole) == active_idx:
                        self._list.setCurrentRow(row)
                        break

            active = self._document.active_layer()
            if active is not None:
                self._opacity.setValue(int(round(active.opacity * 100)))
                self._blend.setCurrentIndex(self._blend.findData(active.blend_mode))
                self._lock_alpha_btn.setChecked(bool(active.lock_alpha))
                self._lock_alpha_btn.setEnabled(True)
            else:
                self._lock_alpha_btn.setChecked(False)
                self._lock_alpha_btn.setEnabled(False)
        finally:
            self._suspend = False

    def _filtered_indices(self) -> set[int]:
        """Return the set of layer indices that survive the search filter."""
        if not self._search_query.strip():
            return set(range(self._document.layer_count))
        return set(self._document.find_layers(self._search_query))

    def _on_search_changed(self, text: str) -> None:  # pragma: no cover - Qt UI
        self._search_query = text
        self.refresh()

    # ---- handlers --------------------------------------------------------

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
        self._document.set_layer_attribute(
            layer_idx, visible=new_visible, name=new_name,
        )

    def _on_add(self) -> None:
        if self._document is None or self._document.layer_count == 0:
            return
        self._document.add_layer()

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
        if self._document is None:
            return
        self._document.remove_active_layer()

    def _on_duplicate(self) -> None:
        if self._document is None:
            return
        self._document.duplicate_active_layer()

    def _on_move(self, *, up: bool) -> None:
        if self._document is None:
            return
        self._document.move_active_layer(up=up)

    def _on_opacity_changed(self, value: int) -> None:
        if self._suspend or self._document is None:
            return
        active_idx = self._document.active_layer_index()
        if active_idx >= 0:
            self._document.set_layer_attribute(active_idx, opacity=value / 100.0)

    def _on_blend_changed(self) -> None:
        if self._suspend or self._document is None:
            return
        active_idx = self._document.active_layer_index()
        if active_idx >= 0:
            self._document.set_layer_attribute(
                active_idx, blend_mode=self._blend.currentData(),
            )

    def _on_lock_alpha_toggled(self, checked: bool) -> None:
        if self._suspend or self._document is None:
            return
        active_idx = self._document.active_layer_index()
        if active_idx >= 0:
            self._document.set_layer_lock_alpha(active_idx, lock_alpha=checked)

    def _row_to_layer_index(self, row: int) -> int:
        if self._document is None:
            return -1
        return self._document.layer_count - 1 - row


# ---------------------------------------------------------------------------
# Navigator dock — minimap of the canvas
# ---------------------------------------------------------------------------


