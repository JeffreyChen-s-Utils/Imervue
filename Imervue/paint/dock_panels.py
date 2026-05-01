"""MediBang-style dock panels for the Paint workspace.

Five docks, each in its own class so they can be added independently to
the QMainWindow. Every panel subscribes to the shared
:class:`Imervue.paint.tool_state.ToolState` singleton so updates from
keyboard shortcuts, the canvas, or another panel propagate correctly.

Phase 1 ships full UI for the panels that are driven entirely by the
tool state (Colour, Brush) and stub UI with placeholder data for the
panels that need wiring to systems built in later phases (Layers,
Navigator, History). Each placeholder explicitly says what it's
waiting for so users aren't confused.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.color_math import (
    hex_to_rgb,
    hsv_to_rgb,
    rgb_to_hex,
    rgb_to_hsv,
)

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

_SWATCH_PX = 22


# ---------------------------------------------------------------------------
# Colour dock
# ---------------------------------------------------------------------------


class ColorDock(QDockWidget):
    """HSB + RGB sliders, hex input, fg/bg swap, recent-colour history."""

    def __init__(self, state: ToolState, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_color", "Color"), parent)
        self._state = state
        self._suspend = False  # re-entrancy guard for slider <-> state sync

        body = QWidget()
        layout = QVBoxLayout(body)

        layout.addLayout(self._build_swatches(lang))
        layout.addLayout(self._build_hsv_form(lang))
        layout.addLayout(self._build_rgb_form(lang))
        layout.addLayout(self._build_hex_row(lang))
        layout.addWidget(self._build_history_label(lang))
        self._history_grid = self._build_history_grid()
        layout.addWidget(self._history_grid)
        layout.addStretch(1)
        self.setWidget(body)

        self._refresh_from_state()
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    # ---- builders --------------------------------------------------------

    def _build_swatches(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        self._fg_swatch = _make_swatch_button()
        self._fg_swatch.clicked.connect(self._pick_fg)
        self._bg_swatch = _make_swatch_button()
        self._bg_swatch.clicked.connect(self._pick_bg)
        swap = QToolButton()
        swap.setText(lang.get("paint_color_swap", "X"))
        swap.setToolTip(lang.get("paint_color_swap_tooltip", "Swap (X)"))
        swap.clicked.connect(self._state.swap_colors)
        reset = QToolButton()
        reset.setText(lang.get("paint_color_reset", "D"))
        reset.setToolTip(lang.get("paint_color_reset_tooltip", "Reset (D)"))
        reset.clicked.connect(self._state.reset_colors)

        row.addWidget(QLabel(lang.get("paint_color_fg", "FG")))
        row.addWidget(self._fg_swatch)
        row.addWidget(QLabel(lang.get("paint_color_bg", "BG")))
        row.addWidget(self._bg_swatch)
        row.addStretch(1)
        row.addWidget(swap)
        row.addWidget(reset)
        return row

    def _build_hsv_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        self._h_slider = _slider(0, 359, 0)
        self._s_slider = _slider(0, 100, 100)
        self._v_slider = _slider(0, 100, 100)
        form.addRow(lang.get("paint_color_h", "H"), self._h_slider)
        form.addRow(lang.get("paint_color_s", "S"), self._s_slider)
        form.addRow(lang.get("paint_color_v", "V"), self._v_slider)
        for s in (self._h_slider, self._s_slider, self._v_slider):
            s.valueChanged.connect(self._on_hsv_changed)
        return form

    def _build_rgb_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        self._r_slider = _slider(0, 255, 0)
        self._g_slider = _slider(0, 255, 0)
        self._b_slider = _slider(0, 255, 0)
        form.addRow(lang.get("paint_color_r", "R"), self._r_slider)
        form.addRow(lang.get("paint_color_g", "G"), self._g_slider)
        form.addRow(lang.get("paint_color_b", "B"), self._b_slider)
        for s in (self._r_slider, self._g_slider, self._b_slider):
            s.valueChanged.connect(self._on_rgb_changed)
        return form

    def _build_hex_row(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.get("paint_color_hex", "Hex")))
        self._hex_edit = QLineEdit()
        self._hex_edit.setMaxLength(7)
        self._hex_edit.editingFinished.connect(self._on_hex_changed)
        row.addWidget(self._hex_edit, stretch=1)
        return row

    @staticmethod
    def _build_history_label(lang: dict) -> QLabel:
        label = QLabel(lang.get("paint_color_history", "Recent"))
        label.setStyleSheet("color: #888;")
        return label

    @staticmethod
    def _build_history_grid() -> QWidget:
        widget = QWidget()
        widget.setLayout(QGridLayout())
        widget.layout().setContentsMargins(0, 0, 0, 0)
        widget.layout().setSpacing(2)
        return widget

    # ---- state sync ------------------------------------------------------

    def _on_state_event(self, channel: str) -> None:
        if channel in (ts.EVENT_COLOR, ts.EVENT_HISTORY):
            self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._suspend = True
        try:
            r, g, b = self._state.foreground
            h, s, v = rgb_to_hsv((r, g, b))
            self._r_slider.setValue(r)
            self._g_slider.setValue(g)
            self._b_slider.setValue(b)
            self._h_slider.setValue(int(round(h)))
            self._s_slider.setValue(int(round(s * 100)))
            self._v_slider.setValue(int(round(v * 100)))
            self._hex_edit.setText(rgb_to_hex(self._state.foreground))
            _paint_swatch(self._fg_swatch, self._state.foreground)
            _paint_swatch(self._bg_swatch, self._state.background)
            self._refresh_history()
        finally:
            self._suspend = False

    def _refresh_history(self) -> None:
        layout: QGridLayout = self._history_grid.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for idx, rgb in enumerate(self._state.color_history):
            btn = _make_swatch_button()
            btn.setProperty("rgb", rgb)
            btn.clicked.connect(
                lambda _checked=False, c=rgb:
                self._state.set_foreground(c, commit=True),
            )
            _paint_swatch(btn, rgb)
            layout.addWidget(btn, idx // 6, idx % 6)

    # ---- handlers --------------------------------------------------------

    def _pick_fg(self) -> None:  # pragma: no cover - Qt UI
        from PySide6.QtWidgets import QColorDialog
        col = QColorDialog.getColor(QColor(*self._state.foreground), self)
        if col.isValid():
            self._state.set_foreground(
                (col.red(), col.green(), col.blue()), commit=True,
            )

    def _pick_bg(self) -> None:  # pragma: no cover - Qt UI
        from PySide6.QtWidgets import QColorDialog
        col = QColorDialog.getColor(QColor(*self._state.background), self)
        if col.isValid():
            self._state.set_background((col.red(), col.green(), col.blue()))

    def _on_hsv_changed(self) -> None:
        if self._suspend:
            return
        rgb = hsv_to_rgb((
            float(self._h_slider.value()),
            self._s_slider.value() / 100.0,
            self._v_slider.value() / 100.0,
        ))
        self._state.set_foreground(rgb)

    def _on_rgb_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_foreground((
            int(self._r_slider.value()),
            int(self._g_slider.value()),
            int(self._b_slider.value()),
        ))

    def _on_hex_changed(self) -> None:
        if self._suspend:
            return
        rgb = hex_to_rgb(self._hex_edit.text())
        if rgb is not None:
            # editingFinished only fires when the user actually
            # commits the hex (Enter / focus out), so this counts as
            # a deliberate colour pick — record it in recents.
            self._state.set_foreground(rgb, commit=True)
        else:
            # Re-display the canonical text for the current foreground.
            self._hex_edit.setText(rgb_to_hex(self._state.foreground))


# ---------------------------------------------------------------------------
# Brush dock
# ---------------------------------------------------------------------------


class BrushDock(QDockWidget):
    """Brush kind, size, opacity, hardness, density, blend mode."""

    def __init__(self, state: ToolState, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_brush", "Brush"), parent)
        self._state = state
        self._suspend = False

        body = QWidget()
        form = QFormLayout(body)

        self._kind = QComboBox()
        for kind in ts.BRUSH_KINDS:
            self._kind.addItem(
                lang.get(f"paint_brush_kind_{kind}", kind.capitalize()),
                userData=kind,
            )
        self._kind.currentIndexChanged.connect(self._on_kind_changed)

        self._size = QSpinBox()
        self._size.setRange(ts.BRUSH_SIZE_MIN, ts.BRUSH_SIZE_MAX)
        self._size.valueChanged.connect(self._on_size_changed)

        self._opacity = _slider(0, 100, 100)
        self._opacity.valueChanged.connect(self._on_opacity_changed)

        self._hardness = _slider(0, 100, 80)
        self._hardness.valueChanged.connect(self._on_hardness_changed)

        self._density = _slider(0, 100, 100)
        self._density.valueChanged.connect(self._on_density_changed)

        self._blend = QComboBox()
        for mode in ts.BLEND_MODES:
            self._blend.addItem(
                lang.get(f"paint_blend_{mode}", mode.replace("_", " ").title()),
                userData=mode,
            )
        self._blend.currentIndexChanged.connect(self._on_blend_changed)

        form.addRow(lang.get("paint_brush_kind", "Kind:"), self._kind)
        form.addRow(lang.get("paint_brush_size", "Size:"), self._size)
        form.addRow(lang.get("paint_brush_opacity", "Opacity:"), self._opacity)
        form.addRow(lang.get("paint_brush_hardness", "Hardness:"), self._hardness)
        form.addRow(lang.get("paint_brush_density", "Density:"), self._density)
        form.addRow(lang.get("paint_brush_blend", "Blend:"), self._blend)

        self.setWidget(body)
        self._refresh_from_state()
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_BRUSH:
            self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._suspend = True
        try:
            self._kind.setCurrentIndex(self._kind.findData(self._state.brush.kind))
            self._size.setValue(self._state.brush.size)
            self._opacity.setValue(int(round(self._state.brush.opacity * 100)))
            self._hardness.setValue(int(round(self._state.brush.hardness * 100)))
            self._density.setValue(int(round(self._state.brush.density * 100)))
            self._blend.setCurrentIndex(self._blend.findData(self._state.brush.blend_mode))
        finally:
            self._suspend = False

    def _on_kind_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(kind=self._kind.currentData())

    def _on_size_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(size=int(self._size.value()))

    def _on_opacity_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(opacity=self._opacity.value() / 100.0)

    def _on_hardness_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(hardness=self._hardness.value() / 100.0)

    def _on_density_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(density=self._density.value() / 100.0)

    def _on_blend_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(blend_mode=self._blend.currentData())


# ---------------------------------------------------------------------------
# Layer dock — placeholder backed by the existing layers system
# ---------------------------------------------------------------------------


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
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setIconSize(
            QPixmap(self._thumbnail_size, self._thumbnail_size).size(),
        )
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list, stretch=1)

        row = QHBoxLayout()
        for key, fallback, slot in (
            ("paint_layers_add", "+", self._on_add),
            ("paint_layers_remove", "−", self._on_remove),
            ("paint_layers_up", "↑", lambda: self._on_move(up=True)),
            ("paint_layers_down", "↓", lambda: self._on_move(up=False)),
            ("paint_layers_duplicate", "⧉", self._on_duplicate),
        ):
            btn = QToolButton()
            btn.setText(lang.get(key, fallback))
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)

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
                # top of the visual list, matching MediBang / Photoshop.
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

    def _row_to_layer_index(self, row: int) -> int:
        if self._document is None:
            return -1
        return self._document.layer_count - 1 - row


# ---------------------------------------------------------------------------
# Navigator dock — minimap of the canvas
# ---------------------------------------------------------------------------


class NavigatorDock(QDockWidget):
    """Mini-map preview of the current canvas with a zoom slider."""

    zoom_changed = Signal(float)
    fit_requested = Signal()

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_navigator", "Navigator"), parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        self._preview = QLabel(lang.get("paint_navigator_no_image", "(no canvas)"))
        self._preview.setMinimumSize(180, 140)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background:#222;color:#888;border:1px solid #333;")
        layout.addWidget(self._preview)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel(lang.get("paint_navigator_zoom", "Zoom:")))
        self._zoom_slider = _slider(5, 800, 100)
        self._zoom_slider.valueChanged.connect(
            lambda v: self.zoom_changed.emit(v / 100.0),
        )
        zoom_row.addWidget(self._zoom_slider, stretch=1)

        fit_btn = QPushButton(lang.get("paint_navigator_fit", "Fit"))
        fit_btn.clicked.connect(self.fit_requested.emit)
        zoom_row.addWidget(fit_btn)

        layout.addLayout(zoom_row)
        layout.addStretch(1)
        self.setWidget(body)

    def set_zoom(self, factor: float) -> None:
        """Update the slider without emitting ``zoom_changed`` again."""
        self._zoom_slider.blockSignals(True)
        try:
            self._zoom_slider.setValue(int(round(factor * 100)))
        finally:
            self._zoom_slider.blockSignals(False)

    def set_preview_image(self, pixmap: QPixmap | None) -> None:
        if pixmap is None or pixmap.isNull():
            self._preview.setPixmap(QPixmap())
            self._preview.setText(language_wrapper.language_word_dict.get(
                "paint_navigator_no_image", "(no canvas)",
            ))
            return
        scaled = pixmap.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setText("")
        self._preview.setPixmap(scaled)


# ---------------------------------------------------------------------------
# History dock — undo/redo log
# ---------------------------------------------------------------------------


class HistoryDock(QDockWidget):
    """Undo / redo log with click-to-jump-to-state."""

    state_selected = Signal(int)

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_history", "History"), parent)

        body = QWidget()
        layout = QVBoxLayout(body)
        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, stretch=1)
        self._hint = QLabel(lang.get(
            "paint_history_empty", "(no undo states yet)",
        ))
        self._hint.setStyleSheet("color: #888;")
        layout.addWidget(self._hint)
        self.setWidget(body)

    def set_states(self, labels: list[str], current_index: int) -> None:
        self._list.clear()
        for label in labels:
            self._list.addItem(QListWidgetItem(label))
        if 0 <= current_index < self._list.count():
            self._list.setCurrentRow(current_index)
        self._hint.setVisible(not labels)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:  # pragma: no cover - Qt UI
        self.state_selected.emit(self._list.row(item))


# ---------------------------------------------------------------------------
# Page navigator dock — multi-page projects
# ---------------------------------------------------------------------------


class PageNavigatorDock(QDockWidget):
    """Page-strip view for a :class:`PaintProject`.

    Shows one row per page (thumbnail + name) plus add / remove /
    move-up / move-down buttons. Clicking a row emits
    :attr:`page_activated` with the page index so the workspace can
    bind that page's document into the canvas.
    """

    page_activated = Signal(int)
    add_requested = Signal()
    remove_requested = Signal(int)
    move_requested = Signal(int, int)   # (src, dst)

    def __init__(self, project=None, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_pages", "Pages"), parent)
        self._project = project

        body = QWidget()
        layout = QVBoxLayout(body)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list, stretch=1)

        row = QHBoxLayout()
        for key, fallback, slot in (
            ("paint_pages_add", "+", self._on_add),
            ("paint_pages_remove", "−", self._on_remove),
            ("paint_pages_up", "↑", lambda: self._on_move(up=True)),
            ("paint_pages_down", "↓", lambda: self._on_move(up=False)),
        ):
            btn = QToolButton()
            btn.setText(lang.get(key, fallback))
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)
        self.setWidget(body)

        self.refresh()

    # ---- public ----------------------------------------------------------

    def set_project(self, project) -> None:
        self._project = project
        self.refresh()

    def project(self):
        return self._project

    def refresh(self) -> None:
        self._list.blockSignals(True)
        try:
            self._list.clear()
            if self._project is None:
                return
            for idx, page in enumerate(self._project.pages):
                self._list.addItem(QListWidgetItem(f"{idx + 1}. {page.name}"))
            active = self._project.active_page_index
            if 0 <= active < self._list.count():
                self._list.setCurrentRow(active)
        finally:
            self._list.blockSignals(False)

    # ---- internals -------------------------------------------------------

    def _on_row_changed(self, row: int) -> None:
        if self._project is None or row < 0:
            return
        if row != self._project.active_page_index:
            self.page_activated.emit(row)

    def _on_add(self) -> None:
        self.add_requested.emit()

    def _on_remove(self) -> None:
        if self._project is None:
            return
        self.remove_requested.emit(self._project.active_page_index)

    def _on_move(self, *, up: bool) -> None:
        if self._project is None:
            return
        src = self._project.active_page_index
        dst = src - 1 if up else src + 1
        if not 0 <= dst < self._project.page_count:
            return
        self.move_requested.emit(src, dst)


# ---------------------------------------------------------------------------
# Material library dock
# ---------------------------------------------------------------------------


class _MaterialThumbnailButton(QToolButton):
    """QToolButton that doubles as a drag source for its material path.

    The dock keeps the click-to-emit ``material_chosen`` signal for
    casual one-click apply; a slow press-and-drag instead starts a
    QDrag carrying the material's path under the imervue MIME type so
    the canvas drop handler can spawn a fresh layer at the drop point.
    """

    def __init__(self, path: str, preview):
        super().__init__()
        self._path = str(path)
        self._preview = preview
        self._press_pos = None

    def mousePressEvent(self, event):  # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # pragma: no cover - Qt UI
        from PySide6.QtCore import QByteArray, QMimeData
        from PySide6.QtGui import QDrag

        from Imervue.paint.material_drop import MATERIAL_MIME_TYPE

        if (
            self._press_pos is None
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            super().mouseMoveEvent(event)
            return
        moved = (event.position().toPoint() - self._press_pos).manhattanLength()
        if moved < 8:
            return
        mime = QMimeData()
        mime.setData(
            MATERIAL_MIME_TYPE,
            QByteArray(self._path.encode("utf-8")),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        if self._preview is not None and not self._preview.isNull():
            drag.setPixmap(self._preview)
        drag.exec(Qt.DropAction.CopyAction)
        self._press_pos = None


class MaterialDock(QDockWidget):
    """Searchable thumbnail grid backed by a :class:`MaterialIndex`.

    The dock owns the visible category tabs and a search box. Clicking
    a thumbnail emits :attr:`material_chosen` with the entry's path
    so a host workspace can route it to the right consumer (pattern
    fill / brush-tip swap / image-paste).
    """

    material_chosen = Signal(str)   # absolute path of the chosen material

    def __init__(self, index=None, parent=None):
        from Imervue.paint.material_library import (
            MATERIAL_CATEGORIES,
            MaterialIndex,
        )

        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_material", "Materials"), parent)
        self._index = index if index is not None else MaterialIndex()
        self._all_categories = MATERIAL_CATEGORIES
        self._active_category: str | None = None

        body = QWidget()
        layout = QVBoxLayout(body)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            lang.get("paint_material_search", "Search materials…"),
        )
        self._search.textChanged.connect(self._refresh_grid)
        layout.addWidget(self._search)

        self._tab_row = QHBoxLayout()
        self._tab_buttons: dict[str | None, QToolButton] = {}
        self._build_tab_buttons()
        layout.addLayout(self._tab_row)

        self._grid_host = QWidget()
        self._grid_layout = QGridLayout(self._grid_host)
        self._grid_layout.setSpacing(4)
        layout.addWidget(self._grid_host, stretch=1)

        self._empty_hint = QLabel(
            lang.get("paint_material_empty", "(no materials yet)"),
        )
        self._empty_hint.setStyleSheet("color: #888;")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_hint)

        self.setWidget(body)
        self._refresh_grid()

    # ---- public ----------------------------------------------------------

    def set_index(self, index) -> None:
        """Replace the index and refresh the grid."""
        self._index = index
        self._build_tab_buttons()
        self._refresh_grid()

    def index(self):
        return self._index

    # ---- internals -------------------------------------------------------

    def _build_tab_buttons(self) -> None:
        """Rebuild the category tab strip from the current index."""
        # Clear existing buttons first.
        while self._tab_row.count():
            child = self._tab_row.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        self._tab_buttons.clear()

        lang = language_wrapper.language_word_dict
        all_btn = QToolButton()
        all_btn.setText(lang.get("paint_material_all", "All"))
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.clicked.connect(lambda: self._on_tab_clicked(None))
        self._tab_row.addWidget(all_btn)
        self._tab_buttons[None] = all_btn
        for category in self._index.categories():
            btn = QToolButton()
            btn.setText(lang.get(
                f"paint_material_cat_{category}", category.replace("_", " ").title(),
            ))
            btn.setCheckable(True)
            btn.clicked.connect(lambda *_, c=category: self._on_tab_clicked(c))
            self._tab_row.addWidget(btn)
            self._tab_buttons[category] = btn
        self._tab_row.addStretch(1)
        self._active_category = None

    def _on_tab_clicked(self, category: str | None) -> None:
        self._active_category = category
        for cat, btn in self._tab_buttons.items():
            btn.setChecked(cat == category)
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        # Clear existing thumbnails.
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        results = self._index.filter(
            category=self._active_category,
            query=self._search.text(),
        )
        self._empty_hint.setVisible(not results)
        cols = 3
        for idx, entry in enumerate(results):
            row, col = divmod(idx, cols)
            btn = self._make_thumbnail(entry)
            self._grid_layout.addWidget(btn, row, col)

    def _make_thumbnail(self, entry) -> QToolButton:
        pix = self._render_thumbnail(entry)
        btn = _MaterialThumbnailButton(str(entry.path), pix)
        btn.setIconSize(QPixmap(64, 64).size())
        btn.setIcon(pix)
        btn.setText(entry.name)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.clicked.connect(
            lambda *_, p=str(entry.path): self.material_chosen.emit(p),
        )
        return btn

    @staticmethod
    def _render_thumbnail(entry) -> QPixmap:
        """Build a 64×64 thumbnail QPixmap from any kind of entry.

        Procedural entries call their provider and convert the numpy
        tile into a QImage. Path-backed entries load via QPixmap
        which handles every Qt-supported image format. Both fall back
        to a neutral placeholder swatch on failure so a broken entry
        never propagates a None into the grid.
        """
        if getattr(entry, "is_procedural", lambda: False)():
            try:
                tile = entry.render()
            except (ValueError, RuntimeError):
                tile = None
            if tile is not None:
                arr = np.ascontiguousarray(tile)
                h, w = arr.shape[:2]
                qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
                pix = QPixmap.fromImage(qimg.copy())
                return pix.scaled(
                    64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        pix = QPixmap(str(entry.path))
        if not pix.isNull():
            return pix.scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        placeholder = QPixmap(64, 64)
        placeholder.fill(QColor("#444"))
        return placeholder


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    return s


def _make_swatch_button() -> QToolButton:
    btn = QToolButton()
    btn.setFixedSize(_SWATCH_PX, _SWATCH_PX)
    btn.setAutoRaise(False)
    return btn


def _paint_swatch(button: QToolButton, rgb: tuple[int, int, int]) -> None:
    pix = QPixmap(_SWATCH_PX, _SWATCH_PX)
    pix.fill(QColor(*rgb))
    painter = QPainter(pix)
    painter.setPen(QColor(0, 0, 0, 80))
    painter.drawRect(0, 0, _SWATCH_PX - 1, _SWATCH_PX - 1)
    painter.end()
    button.setIcon(pix)
    button.setIconSize(pix.size())


# ---------------------------------------------------------------------------
# Layer-row presentation helpers
# ---------------------------------------------------------------------------


_LAYER_LABEL_GLYPHS = {
    "red": "🟥",
    "orange": "🟧",
    "yellow": "🟨",
    "green": "🟩",
    "blue": "🟦",
    "violet": "🟪",
    "grey": "⬜",
}


def _label_with_color_chip(layer) -> str:
    """Return ``layer.name`` prefixed with the colour-label glyph.

    The glyph approach keeps the LayerDock readable in plain-text
    accessibility tools (no custom QStandardItem needed), and the
    chip survives the existing ``itemChanged`` rename path because
    Qt always presents the full string back to ``_on_item_changed``.
    """
    label = getattr(layer, "color_label", None)
    name = layer.name
    glyph = _LAYER_LABEL_GLYPHS.get(label or "")
    if glyph is None:
        return name
    return f"{glyph} {name}"


def _strip_color_chip(text: str) -> str:
    """Remove the leading colour-chip glyph + space from ``text``.

    Inverse of :func:`_label_with_color_chip`. Keeps the persisted
    layer name free of emoji even after the user inline-edits a row
    that already had a chip prefix.
    """
    for glyph in _LAYER_LABEL_GLYPHS.values():
        prefix = f"{glyph} "
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _array_to_icon(thumb: np.ndarray) -> QIcon:
    """Wrap an HxWx4 RGBA buffer into a QIcon for the LayerDock list."""
    h, w = thumb.shape[:2]
    qimage = QImage(
        bytes(thumb.tobytes()),
        w, h, w * 4, QImage.Format.Format_RGBA8888,
    )
    return QIcon(QPixmap.fromImage(qimage))
