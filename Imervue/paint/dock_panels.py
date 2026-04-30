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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
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
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_layers", "Layers"), parent)
        self._document = document
        self._suspend = False

        body = QWidget()
        layout = QVBoxLayout(body)

        self._list = QListWidget()
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
            for idx, layer in enumerate(self._document.layers()):
                # Stack drawn top-down — most-recently-added layer at the
                # top of the visual list, matching MediBang / Photoshop.
                row_index = self._document.layer_count - 1 - idx
                item = QListWidgetItem(layer.name)
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEditable,
                )
                item.setCheckState(
                    Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked,
                )
                item.setData(Qt.ItemDataRole.UserRole, idx)
                self._list.insertItem(row_index, item)
            active_row = (
                self._document.layer_count - 1 - self._document.active_layer_index()
            )
            self._list.setCurrentRow(max(0, active_row))

            active = self._document.active_layer()
            if active is not None:
                self._opacity.setValue(int(round(active.opacity * 100)))
                self._blend.setCurrentIndex(self._blend.findData(active.blend_mode))
        finally:
            self._suspend = False

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
        new_name = item.text()
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
