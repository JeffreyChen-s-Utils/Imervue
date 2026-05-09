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
    QMenu,
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

# Restore-from-transparent fallbacks used when the user toggles a
# slot to ``None`` without ever having set a colour first. Black for
# FG and white for BG mirror the historical paint defaults.
DEFAULT_FG_FALLBACK = (0, 0, 0)
DEFAULT_BG_FALLBACK = (255, 255, 255)

# Style sheet shared by the dim "hint" / placeholder labels in
# multiple docks. Module-level so a future palette change updates
# every callsite at once.
_HINT_LABEL_STYLE = "color: #888;"


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
        # Last opaque colour for each slot — restored when the user
        # toggles "transparent" off again.
        self._stashed_fg: tuple[int, int, int] | None = None
        self._stashed_bg: tuple[int, int, int] | None = None

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
        self._fg_swatch.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._fg_swatch.customContextMenuRequested.connect(
            lambda _pos: self._show_swatch_menu(self._fg_swatch, fg=True),
        )
        self._fg_swatch.setToolTip(lang.get(
            "paint_color_fg_tooltip",
            "Foreground (paint colour) — click to pick, right-click for transparent",
        ))
        self._bg_swatch = _make_swatch_button()
        self._bg_swatch.clicked.connect(self._pick_bg)
        self._bg_swatch.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._bg_swatch.customContextMenuRequested.connect(
            lambda _pos: self._show_swatch_menu(self._bg_swatch, fg=False),
        )
        self._bg_swatch.setToolTip(lang.get(
            "paint_color_bg_tooltip",
            "Background (gradient end, X-swap target) — "
            "click to pick, right-click for transparent",
        ))
        swap = QToolButton()
        swap.setText(lang.get("paint_color_swap", "X"))
        swap.setToolTip(lang.get("paint_color_swap_tooltip", "Swap (X)"))
        swap.clicked.connect(self._state.swap_colors)
        reset = QToolButton()
        reset.setText(lang.get("paint_color_reset", "D"))
        reset.setToolTip(lang.get("paint_color_reset_tooltip", "Reset (D)"))
        reset.clicked.connect(self._state.reset_colors)
        # Single-click "transparent / no colour" toggle. Cycles each
        # slot between its current colour and ``None`` so the user
        # doesn't have to dig through a context menu when they just
        # want a clean fade-to-transparent gradient.
        self._transparent_btn = QToolButton()
        self._transparent_btn.setText(
            lang.get("paint_color_transparent", "∅"),
        )
        self._transparent_btn.setToolTip(
            lang.get(
                "paint_color_transparent_tooltip",
                "Toggle BG transparent (right-click swatch for FG)",
            ),
        )
        self._transparent_btn.clicked.connect(self._toggle_bg_transparent)

        row.addWidget(QLabel(lang.get("paint_color_fg", "FG")))
        row.addWidget(self._fg_swatch)
        row.addWidget(QLabel(lang.get("paint_color_bg", "BG")))
        row.addWidget(self._bg_swatch)
        row.addStretch(1)
        row.addWidget(self._transparent_btn)
        row.addWidget(swap)
        row.addWidget(reset)
        return row

    def _toggle_bg_transparent(self) -> None:
        """Click handler: flip BG between its current colour and ``None``.

        Stashes the previous BG so the toggle round-trips — a second
        click restores whatever colour was active. The stash persists
        for the lifetime of the dock; closing and re-opening starts
        fresh.
        """
        if self._state.background is None:
            self._state.set_background(self._stashed_bg or DEFAULT_BG_FALLBACK)
        else:
            self._stashed_bg = self._state.background
            self._state.set_background(None)

    def _show_swatch_menu(self, swatch, *, fg: bool) -> None:  # pragma: no cover - Qt UI
        """Right-click context menu on either swatch — currently just
        the "Transparent" toggle for whichever slot was clicked."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(swatch)
        label = "Transparent"
        action = menu.addAction(label)
        action.setCheckable(True)
        if fg:
            action.setChecked(self._state.foreground is None)
            action.triggered.connect(self._toggle_fg_transparent)
        else:
            action.setChecked(self._state.background is None)
            action.triggered.connect(self._toggle_bg_transparent)
        menu.exec(swatch.mapToGlobal(swatch.rect().bottomLeft()))

    def _toggle_fg_transparent(self) -> None:
        if self._state.foreground is None:
            self._state.set_foreground(self._stashed_fg or DEFAULT_FG_FALLBACK)
        else:
            self._stashed_fg = self._state.foreground
            self._state.set_foreground(None)

    def _build_hsv_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        self._h_slider = _slider(0, 359, 0)
        self._s_slider = _slider(0, 100, 100)
        self._v_slider = _slider(0, 100, 100)
        self._h_slider.setToolTip(lang.get(
            "paint_color_h_tooltip", "Hue (0–359°)",
        ))
        self._s_slider.setToolTip(lang.get(
            "paint_color_s_tooltip", "Saturation (0–100%)",
        ))
        self._v_slider.setToolTip(lang.get(
            "paint_color_v_tooltip", "Value / brightness (0–100%)",
        ))
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
        self._r_slider.setToolTip(lang.get(
            "paint_color_r_tooltip", "Red channel (0–255)",
        ))
        self._g_slider.setToolTip(lang.get(
            "paint_color_g_tooltip", "Green channel (0–255)",
        ))
        self._b_slider.setToolTip(lang.get(
            "paint_color_b_tooltip", "Blue channel (0–255)",
        ))
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
        self._hex_edit.setToolTip(lang.get(
            "paint_color_hex_tooltip",
            "CSS hex (e.g. #FF8800) — Enter or Tab commits and pushes to recents",
        ))
        row.addWidget(self._hex_edit, stretch=1)
        return row

    @staticmethod
    def _build_history_label(lang: dict) -> QLabel:
        label = QLabel(lang.get("paint_color_history", "Recent"))
        label.setStyleSheet(_HINT_LABEL_STYLE)
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
            # Sliders / hex echo the foreground numerically. When
            # foreground is "transparent" (None) there is no number
            # to mirror — leave the previous slider positions in
            # place and blank out the hex edit so the user has a
            # clear cue that the active foreground is the no-colour
            # slot.
            fg = self._state.foreground
            if fg is None:
                self._hex_edit.setText("")
            else:
                r, g, b = fg
                h, s, v = rgb_to_hsv((r, g, b))
                self._r_slider.setValue(r)
                self._g_slider.setValue(g)
                self._b_slider.setValue(b)
                self._h_slider.setValue(int(round(h)))
                self._s_slider.setValue(int(round(s * 100)))
                self._v_slider.setValue(int(round(v * 100)))
                self._hex_edit.setText(rgb_to_hex(fg))
            _paint_swatch(self._fg_swatch, fg)
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
        seed = self._state.foreground or (0, 0, 0)
        col = QColorDialog.getColor(QColor(*seed), self)
        if col.isValid():
            self._state.set_foreground(
                (col.red(), col.green(), col.blue()), commit=True,
            )

    def _pick_bg(self) -> None:  # pragma: no cover - Qt UI
        from PySide6.QtWidgets import QColorDialog
        seed = self._state.background or (255, 255, 255)
        col = QColorDialog.getColor(QColor(*seed), self)
        if col.isValid():
            self._state.set_background((col.red(), col.green(), col.blue()))

    def _set_fg_transparent(self) -> None:
        """Toggle the foreground to "transparent / no colour"."""
        self._state.set_foreground(None)

    def _set_bg_transparent(self) -> None:
        """Toggle the background to "transparent / no colour"."""
        self._state.set_background(None)

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
            # Blank when foreground is "transparent" (no number to echo).
            fg = self._state.foreground
            self._hex_edit.setText("" if fg is None else rgb_to_hex(fg))


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
        # Tall enough to host the brush-kind preview thumbnail; the
        # combo's icon size has to be set before the items go in or
        # the icons render at QStyle's default ~16px.
        from PySide6.QtCore import QSize
        from Imervue.paint.brush_kind_preview import (
            DEFAULT_THUMBNAIL_H,
            DEFAULT_THUMBNAIL_W,
            render_brush_kind_pixmap,
        )
        self._kind.setIconSize(QSize(DEFAULT_THUMBNAIL_W, DEFAULT_THUMBNAIL_H))
        from PySide6.QtGui import QIcon
        for kind in ts.BRUSH_KINDS:
            try:
                icon = QIcon(render_brush_kind_pixmap(kind))
            except (RuntimeError, ValueError):
                icon = QIcon()
            self._kind.addItem(
                icon,
                lang.get(f"paint_brush_kind_{kind}", kind.capitalize()),
                userData=kind,
            )
        self._kind.currentIndexChanged.connect(self._on_kind_changed)
        self._kind.setToolTip(lang.get(
            "paint_brush_kind_tooltip",
            "Brush family — pen / pencil / marker / airbrush / watercolor",
        ))

        self._size = QSpinBox()
        self._size.setRange(ts.BRUSH_SIZE_MIN, ts.BRUSH_SIZE_MAX)
        self._size.valueChanged.connect(self._on_size_changed)
        self._size.setToolTip(lang.get(
            "paint_brush_size_tooltip",
            "Brush diameter in canvas pixels — [ smaller, ] larger",
        ))

        self._opacity = _slider(0, 100, 100)
        self._opacity.valueChanged.connect(self._on_opacity_changed)
        self._opacity.setToolTip(lang.get(
            "paint_brush_opacity_tooltip",
            "Per-dab paint coverage (0–100%)",
        ))

        self._hardness = _slider(0, 100, 80)
        self._hardness.valueChanged.connect(self._on_hardness_changed)
        self._hardness.setToolTip(lang.get(
            "paint_brush_hardness_tooltip",
            "Edge falloff — 0% soft, 100% hard disc",
        ))

        self._density = _slider(0, 100, 100)
        self._density.valueChanged.connect(self._on_density_changed)
        self._density.setToolTip(lang.get(
            "paint_brush_density_tooltip",
            "Per-dab opacity multiplier — lower deposits less ink per stamp",
        ))

        # Stabilizer / scatter / colour-jitter / follow-tilt — engine
        # already supports these via brush_dynamics + brush_random;
        # surfacing them as live controls here matches MediBang's
        # brush-options panel.
        self._stabilizer = _slider(0, 100, 0)
        self._stabilizer.valueChanged.connect(self._on_stabilizer_changed)
        self._stabilizer.setToolTip(lang.get(
            "paint_brush_stabilizer_tooltip",
            "Smooth jittery input — 0 off, 100 maximum lag for a clean line",
        ))

        self._scatter = _slider(0, 100, 0)
        self._scatter.valueChanged.connect(self._on_scatter_changed)
        self._scatter.setToolTip(lang.get(
            "paint_brush_scatter_tooltip",
            "Random per-dab offset, as a fraction of brush size",
        ))

        self._color_jitter = _slider(0, 100, 0)
        self._color_jitter.valueChanged.connect(self._on_color_jitter_changed)
        self._color_jitter.setToolTip(lang.get(
            "paint_brush_color_jitter_tooltip",
            "Random hue / luma drift along the stroke",
        ))

        from PySide6.QtWidgets import QCheckBox
        self._follow_tilt = QCheckBox(
            lang.get("paint_brush_follow_tilt", "Follow pen tilt"),
        )
        self._follow_tilt.toggled.connect(self._on_follow_tilt_changed)
        self._follow_tilt.setToolTip(lang.get(
            "paint_brush_follow_tilt_tooltip",
            "Stretch the brush kernel along the tablet pen tilt direction",
        ))

        self._blend = QComboBox()
        for mode in ts.BLEND_MODES:
            self._blend.addItem(
                lang.get(f"paint_blend_{mode}", mode.replace("_", " ").title()),
                userData=mode,
            )
        self._blend.currentIndexChanged.connect(self._on_blend_changed)
        self._blend.setToolTip(lang.get(
            "paint_brush_blend_tooltip",
            "Compositing mode applied at every dab — Normal is alpha-over",
        ))

        form.addRow(lang.get("paint_brush_kind", "Kind:"), self._kind)
        form.addRow(lang.get("paint_brush_size", "Size:"), self._size)
        form.addRow(lang.get("paint_brush_opacity", "Opacity:"), self._opacity)
        form.addRow(lang.get("paint_brush_hardness", "Hardness:"), self._hardness)
        form.addRow(lang.get("paint_brush_density", "Density:"), self._density)
        form.addRow(
            lang.get("paint_brush_stabilizer", "Stabilizer:"),
            self._stabilizer,
        )
        form.addRow(
            lang.get("paint_brush_scatter", "Scatter:"), self._scatter,
        )
        form.addRow(
            lang.get("paint_brush_color_jitter", "Colour jitter:"),
            self._color_jitter,
        )
        form.addRow("", self._follow_tilt)
        form.addRow(lang.get("paint_brush_blend", "Blend:"), self._blend)

        # MediBang-style sub-tool / preset manager. The button opens a
        # modal dialog that drives ``state.add_sub_tool`` /
        # ``apply_sub_tool`` / ``remove_sub_tool`` for the active main
        # tool, so brush + fill snapshots round-trip through the
        # existing persistence path.
        self._presets_btn = QPushButton(
            lang.get("paint_brush_presets_open", "Presets…"),
        )
        self._presets_btn.clicked.connect(self._on_presets_clicked)
        form.addRow("", self._presets_btn)

        self.setWidget(body)
        self._refresh_from_state()
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    def _on_presets_clicked(self) -> None:
        from Imervue.paint.brush_preset_dialog import open_brush_preset_dialog
        open_brush_preset_dialog(self._state, parent=self)

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
            self._stabilizer.setValue(
                int(round(self._state.brush.stabilizer * 100)),
            )
            self._scatter.setValue(
                int(round(self._state.brush.scatter * 100)),
            )
            self._color_jitter.setValue(
                int(round(self._state.brush.color_jitter * 100)),
            )
            self._follow_tilt.setChecked(
                bool(self._state.brush.follow_tilt),
            )
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

    def _on_stabilizer_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(stabilizer=self._stabilizer.value() / 100.0)

    def _on_scatter_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(scatter=self._scatter.value() / 100.0)

    def _on_color_jitter_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(
            color_jitter=self._color_jitter.value() / 100.0,
        )

    def _on_follow_tilt_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_brush(follow_tilt=bool(checked))

    def _on_blend_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(blend_mode=self._blend.currentData())


# ---------------------------------------------------------------------------
# Fill bucket options dock
# ---------------------------------------------------------------------------


class FillDock(QDockWidget):
    """Surfaces every :class:`FillSettings` knob for the bucket tool.

    Tabified next to BrushDock so the user flips between brush and
    bucket option panels the way MediBang Paint Pro does. Updates
    flow both ways: state-event subscription mirrors the singleton
    when the user changes settings via shortcut or another panel,
    and edits here go through ``state.set_fill(...)`` so persistence
    + redraw fire on a single code path.
    """

    def __init__(self, state: ToolState, parent=None):
        from PySide6.QtWidgets import QCheckBox
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_fill", "Bucket"), parent)
        self._state = state
        self._suspend = False

        body = QWidget()
        form = QFormLayout(body)

        self._tolerance = _slider(0, 255, 32)
        self._tolerance.valueChanged.connect(self._on_tolerance_changed)
        self._tolerance.setToolTip(lang.get(
            "paint_fill_tolerance_tooltip",
            "Per-channel colour distance accepted as the same region "
            "(0 exact, 255 anything)",
        ))

        self._contiguous = QCheckBox(
            lang.get("paint_fill_contiguous", "Contiguous (only adjacent pixels)"),
        )
        self._contiguous.toggled.connect(self._on_contiguous_changed)
        self._contiguous.setToolTip(lang.get(
            "paint_fill_contiguous_tooltip",
            "On: only pixels reachable from the click. Off: every "
            "matching pixel canvas-wide.",
        ))

        self._sample_all = QCheckBox(
            lang.get("paint_fill_sample_all", "Sample all layers"),
        )
        self._sample_all.toggled.connect(self._on_sample_all_changed)
        self._sample_all.setToolTip(lang.get(
            "paint_fill_sample_all_tooltip",
            "Match colours against the visible composite instead of "
            "just the active layer",
        ))

        self._use_reference = QCheckBox(
            lang.get(
                "paint_fill_use_reference",
                "Use reference layer for boundaries",
            ),
        )
        self._use_reference.toggled.connect(self._on_use_reference_changed)
        self._use_reference.setToolTip(lang.get(
            "paint_fill_use_reference_tooltip",
            "Read connectivity from the document's pinned reference "
            "layer (e.g. line art) so fill stops at ink boundaries "
            "regardless of the active layer's colour",
        ))

        self._expand = _slider(ts.FILL_EXPAND_MIN, ts.FILL_EXPAND_MAX, 0)
        self._expand.valueChanged.connect(self._on_expand_changed)
        self._expand.setToolTip(lang.get(
            "paint_fill_expand_tooltip",
            "Dilate the fill by N pixels after computing it — bridges "
            "the anti-aliased halo around lineart",
        ))

        self._gap_close = _slider(
            ts.FILL_GAP_CLOSE_MIN, ts.FILL_GAP_CLOSE_MAX, 0,
        )
        self._gap_close.valueChanged.connect(self._on_gap_close_changed)
        self._gap_close.setToolTip(lang.get(
            "paint_fill_gap_close_tooltip",
            "Bridge gaps in the lineart up to N pixels wide so fill "
            "doesn't leak through broken pen strokes",
        ))

        form.addRow(
            lang.get("paint_fill_tolerance", "Tolerance:"), self._tolerance,
        )
        form.addRow("", self._contiguous)
        form.addRow("", self._sample_all)
        form.addRow("", self._use_reference)
        form.addRow(
            lang.get("paint_fill_expand", "Expand (px):"), self._expand,
        )
        form.addRow(
            lang.get("paint_fill_gap_close", "Close gap (px):"),
            self._gap_close,
        )

        # MediBang-style "fill every closed region in one click". Goes
        # to a workspace-level action so it can read the active layer
        # + the reference layer through the document API. The button
        # surfaces a no-op + status message when no callback is wired.
        self._auto_fill_btn = QPushButton(
            lang.get("paint_fill_auto_regions", "Auto-fill closed regions"),
        )
        self._auto_fill_btn.clicked.connect(self._on_auto_fill_clicked)
        form.addRow("", self._auto_fill_btn)
        self._auto_fill_callback = None

        self.setWidget(body)
        self._refresh_from_state()
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    def set_auto_fill_callback(self, callback) -> None:
        """Wire the workspace's auto-fill verb to the dock's button."""
        self._auto_fill_callback = callback

    def _on_auto_fill_clicked(self) -> None:
        if self._auto_fill_callback is None:
            return
        self._auto_fill_callback()

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_FILL:
            self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._suspend = True
        try:
            fill = self._state.fill
            self._tolerance.setValue(int(fill.tolerance))
            self._contiguous.setChecked(bool(fill.contiguous))
            self._sample_all.setChecked(bool(fill.sample_all_layers))
            self._use_reference.setChecked(bool(fill.use_reference_layer))
            self._expand.setValue(int(fill.expand_px))
            self._gap_close.setValue(int(fill.gap_close_px))
        finally:
            self._suspend = False

    def _on_tolerance_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_fill(tolerance=int(self._tolerance.value()))

    def _on_contiguous_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_fill(contiguous=bool(checked))

    def _on_sample_all_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_fill(sample_all_layers=bool(checked))

    def _on_use_reference_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_fill(use_reference_layer=bool(checked))

    def _on_expand_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_fill(expand_px=int(self._expand.value()))

    def _on_gap_close_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_fill(gap_close_px=int(self._gap_close.value()))


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
        # Dedicated "add adjustment layer" entry — MediBang's Layer
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
        self._zoom_slider.setToolTip(lang.get(
            "paint_navigator_zoom_tooltip",
            "Drag to zoom the canvas (5–800%) — same as Ctrl+wheel "
            "but with a numeric scrub",
        ))
        zoom_row.addWidget(self._zoom_slider, stretch=1)

        fit_btn = QPushButton(lang.get("paint_navigator_fit", "Fit"))
        fit_btn.clicked.connect(self.fit_requested.emit)
        # Pull the live binding from the registry so the tooltip stays
        # in sync if the user remaps Fit View.
        from Imervue.paint.shortcut_registry import load_shortcuts
        try:
            fit_key = load_shortcuts().get("paint.view.fit")
        except KeyError:
            fit_key = ""
        base_tip = lang.get(
            "paint_navigator_fit_tooltip",
            "Reset the canvas to fit the viewport",
        )
        fit_btn.setToolTip(f"{base_tip} ({fit_key})" if fit_key else base_tip)
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
        self._hint.setStyleSheet(_HINT_LABEL_STYLE)
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
        for key, fallback, slot, tooltip_key, tooltip_fallback in (
            ("paint_pages_add", "+", self._on_add,
             "paint_pages_add_tooltip", "Add page"),
            ("paint_pages_remove", "−", self._on_remove,
             "paint_pages_remove_tooltip", "Delete page"),
            ("paint_pages_up", "↑", lambda: self._on_move(up=True),
             "paint_pages_up_tooltip", "Move page up"),
            ("paint_pages_down", "↓", lambda: self._on_move(up=False),
             "paint_pages_down_tooltip", "Move page down"),
        ):
            btn = QToolButton()
            btn.setText(lang.get(key, fallback))
            btn.setToolTip(lang.get(tooltip_key, tooltip_fallback))
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
        self._empty_hint.setStyleSheet(_HINT_LABEL_STYLE)
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


def _paint_swatch(
    button: QToolButton,
    rgb: tuple[int, int, int] | None,
) -> None:
    """Render a colour-chip icon on ``button``.

    ``rgb=None`` represents "transparent / no colour" and renders a
    grey checker pattern with a red diagonal slash — the same idiom
    Photoshop / Krita / MediBang use for "no fill" so users can
    spot the transparent slot at a glance.
    """
    pix = QPixmap(_SWATCH_PX, _SWATCH_PX)
    if rgb is None:
        pix.fill(QColor(255, 255, 255))
        painter = QPainter(pix)
        # Light-grey checker pattern.
        cell = 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 200, 200))
        for y in range(0, _SWATCH_PX, cell):
            for x in range(0, _SWATCH_PX, cell):
                if ((x // cell) + (y // cell)) % 2 == 0:
                    painter.drawRect(x, y, cell, cell)
        # Red slash for the universal "no colour" affordance.
        from PySide6.QtGui import QPen
        pen = QPen(QColor(220, 40, 40))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(2, _SWATCH_PX - 3, _SWATCH_PX - 3, 2)
        painter.setPen(QColor(0, 0, 0, 120))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, _SWATCH_PX - 1, _SWATCH_PX - 1)
        painter.end()
    else:
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
