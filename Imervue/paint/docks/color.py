"""Colour picker dock."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

from Imervue.paint.docks._helpers import (
    DEFAULT_BG_FALLBACK,
    DEFAULT_FG_FALLBACK,
    _HINT_LABEL_STYLE,
    _make_swatch_button,
    _paint_swatch,
    _slider,
)


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
        """Right-click context menu — Transparent toggle plus Copy hex
        for the slot's current colour. Copy stays disabled when the
        slot is already transparent so we don't put the literal string
        ``None`` on the clipboard."""
        from PySide6.QtWidgets import QApplication
        lang = language_wrapper.language_word_dict
        menu = QMenu(swatch)
        transparent_action = menu.addAction(
            lang.get("paint_color_transparent", "Transparent"),
        )
        transparent_action.setCheckable(True)
        slot_value = self._state.foreground if fg else self._state.background
        transparent_action.setChecked(slot_value is None)
        if fg:
            transparent_action.triggered.connect(self._toggle_fg_transparent)
        else:
            transparent_action.triggered.connect(self._toggle_bg_transparent)
        menu.addSeparator()
        copy_action = menu.addAction(
            lang.get("paint_color_copy_hex", "Copy as #RRGGBB"),
        )
        copy_action.setEnabled(slot_value is not None)
        if slot_value is not None:
            copy_action.triggered.connect(
                lambda _checked=False, rgb=slot_value: QApplication.clipboard().setText(
                    f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}",
                ),
            )
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


