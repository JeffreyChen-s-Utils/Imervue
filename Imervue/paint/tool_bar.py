"""full-featured tool bars for the Paint workspace.

Two pieces:

* :class:`PaintToolBar` — vertical icon bar listing every tool
  registered in :data:`Imervue.paint.tool_state.TOOLS`. Buttons are
  exclusive (mutually checkable). Clicking flips
  :attr:`ToolState.tool` which causes the rest of the workspace to
  react.
* :class:`PaintOptionsBar` — horizontal context-sensitive strip that
  swaps its inner widget when the active tool changes. Phase 1 ships
  a fully wired brush / eraser strip and stubs for the remaining
  tools; Phase 2 plugs the rest in.

Tool labels live in the language dictionary under ``paint_tool_*``
keys so translations follow the rest of the app.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.gradient import GRADIENT_KINDS
from Imervue.paint.selection import SELECTION_MODES
from Imervue.paint.tools_menu import tool_shortcut

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


# ---------------------------------------------------------------------------
# Tool ordering — the left bar walks this list in order so additions slot in
# without breaking layout. Separators are inserted at the documented
# breakpoints to mirror raster paint apps' visual grouping.
# ---------------------------------------------------------------------------
TOOL_ORDER = (
    "brush", "eraser", "fill", "eyedropper",
    None,             # ── group break
    "select_rect", "select_lasso", "select_wand", "select_quick", "move",
    None,             # ── group break
    "text", "gradient", "blur", "smudge", "dodge", "burn", "sponge",
    "bezier_pen", "clone_stamp", "speech_bubble",
    "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
    "crop", "transform",
    None,             # ── group break
    "hand", "zoom",
)


class PaintToolBar(QToolBar):
    """Vertical exclusive-checkable bar of every tool.

    Use :meth:`set_active_tool` to keep the visible selection in sync
    with external changes (keyboard shortcut, programmatic switch).
    """

    tool_picked = Signal(str)

    def __init__(self, state: ToolState, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_toolbar_title", "Paint Tools"), parent)
        self._state = state
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMovable(False)
        self.setFloatable(False)

        self._group = QActionGroup(self)
        self._group.setExclusive(True)
        self._actions: dict[str, QAction] = {}

        for entry in TOOL_ORDER:
            if entry is None:
                self.addSeparator()
                continue
            self._add_tool_action(entry, lang)

        self.set_active_tool(state.tool)
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    def set_active_tool(self, tool: str) -> None:
        action = self._actions.get(tool)
        if action is None:
            return
        action.setChecked(True)

    def action_for(self, tool: str) -> QAction | None:
        return self._actions.get(tool)

    def show_tool_keys(self, bindings: Mapping[str, str]) -> None:
        """Name the user's remapped keys (``ShortcutRegistry`` items) in the tooltips."""
        for tool, action in self._actions.items():
            _show_key(action, tool_shortcut(tool, bindings))

    # ---- internals -------------------------------------------------------

    def _add_tool_action(self, tool: str, lang: dict) -> None:
        label = lang.get(f"paint_tool_{tool}", tool.replace("_", " ").title())
        action = QAction(label, self)
        action.setCheckable(True)
        action.setActionGroup(self._group)
        # The Tools menu owns the key (a second QAction on the same key makes
        # Qt treat it as ambiguous and fire neither); the button only shows it.
        _show_key(action, tool_shortcut(tool))
        action.triggered.connect(lambda checked=False, t=tool: self._on_tool_clicked(t))
        self.addAction(action)
        self._actions[tool] = action

    def _on_tool_clicked(self, tool: str) -> None:
        if self._state.set_tool(tool):
            self.tool_picked.emit(tool)

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_TOOL:
            self.set_active_tool(self._state.tool)


def _show_key(action: QAction, key: str) -> None:
    label = action.text()
    action.setToolTip(f"{label} ({key})" if key else label)


# ---------------------------------------------------------------------------
# Top options bar — content swaps when the tool changes
# ---------------------------------------------------------------------------


class PaintOptionsBar(QToolBar):
    """Context-sensitive options strip; swaps inner widget per tool."""

    def __init__(self, state: ToolState, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_options_title", "Tool Options"), parent)
        self._state = state
        self._suspend = False
        self.setMovable(False)
        self.setFloatable(False)

        self._stack = QStackedWidget()
        self._page_for_tool: dict[str, int] = {}

        # Brush / eraser share the same strip — size/opacity/hardness sliders.
        brush_idx = self._stack.addWidget(self._build_brush_strip(lang))
        for tool in ("brush", "eraser"):
            self._page_for_tool[tool] = brush_idx

        # Fill bucket — tolerance + contiguous + sample-all-layers
        fill_idx = self._stack.addWidget(self._build_fill_strip(lang))
        self._page_for_tool["fill"] = fill_idx

        # Selection — replace / add / subtract / intersect
        select_idx = self._stack.addWidget(self._build_selection_strip(lang))
        for tool in ("select_rect", "select_lasso", "select_wand", "select_quick"):
            self._page_for_tool[tool] = select_idx

        # Gradient — kind + reverse
        gradient_idx = self._stack.addWidget(self._build_gradient_strip(lang))
        self._page_for_tool["gradient"] = gradient_idx

        # Empty page for tools with no options yet (move / hand / zoom / blur / smudge / eyedropper)
        empty_idx = self._stack.addWidget(self._build_empty_strip(lang))
        for tool in (
            "eyedropper", "move", "hand", "zoom", "blur", "smudge", "text",
            "dodge", "burn", "sponge",
            "bezier_pen", "clone_stamp", "transform", "speech_bubble",
            "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
            "crop",
        ):
            self._page_for_tool[tool] = empty_idx

        self.addWidget(self._stack)
        self.set_tool(state.tool)
        self._refresh_brush_strip()
        self._refresh_option_strips()

        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    # ---- public ----------------------------------------------------------

    def set_tool(self, tool: str) -> None:
        idx = self._page_for_tool.get(tool)
        if idx is not None:
            self._stack.setCurrentIndex(idx)

    # ---- builders --------------------------------------------------------

    def _build_brush_strip(self, lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)

        row.addWidget(QLabel(lang.get("paint_brush_size", "Size:")))
        self._brush_size = QSpinBox()
        self._brush_size.setRange(ts.BRUSH_SIZE_MIN, ts.BRUSH_SIZE_MAX)
        self._brush_size.valueChanged.connect(self._on_brush_size)
        self._brush_size.setToolTip(lang.get(
            "paint_brush_size_tooltip",
            "Brush diameter in canvas pixels — [ smaller, ] larger",
        ))
        row.addWidget(self._brush_size)

        row.addWidget(QLabel(lang.get("paint_brush_opacity", "Opacity:")))
        self._brush_opacity = _slider(0, 100, 100)
        self._brush_opacity.valueChanged.connect(self._on_brush_opacity)
        self._brush_opacity.setToolTip(lang.get(
            "paint_brush_opacity_tooltip",
            "Per-dab paint coverage (0–100%)",
        ))
        row.addWidget(self._brush_opacity)

        row.addWidget(QLabel(lang.get("paint_brush_hardness", "Hardness:")))
        self._brush_hardness = _slider(0, 100, 80)
        self._brush_hardness.valueChanged.connect(self._on_brush_hardness)
        self._brush_hardness.setToolTip(lang.get(
            "paint_brush_hardness_tooltip",
            "Edge falloff — 0% soft, 100% hard disc",
        ))
        row.addWidget(self._brush_hardness)

        row.addStretch(1)
        return widget

    def _build_fill_strip(self, lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_fill_tolerance", "Tolerance:")))
        self._fill_tolerance = _slider(0, 255, self._state.fill.tolerance)
        self._fill_tolerance.setToolTip(lang.get(
            "paint_fill_tolerance_tooltip",
            "Per-channel colour distance accepted as the same region (0 exact, 255 anything)",
        ))
        self._fill_tolerance.valueChanged.connect(
            lambda value: self._set_fill(tolerance=int(value)))
        row.addWidget(self._fill_tolerance)
        self._fill_contiguous = QCheckBox(lang.get("paint_fill_contiguous", "Contiguous"))
        self._fill_contiguous.setToolTip(lang.get(
            "paint_fill_contiguous_tooltip",
            "On: only pixels reachable from the click. Off: every matching pixel canvas-wide.",
        ))
        self._fill_contiguous.toggled.connect(
            lambda checked: self._set_fill(contiguous=bool(checked)))
        row.addWidget(self._fill_contiguous)
        self._fill_all_layers = QCheckBox(
            lang.get("paint_fill_all_layers", "Sample all layers"),
        )
        self._fill_all_layers.setToolTip(lang.get(
            "paint_fill_all_layers_tooltip",
            "Use the visible composite for the colour match instead of just the active layer",
        ))
        self._fill_all_layers.toggled.connect(
            lambda checked: self._set_fill(sample_all_layers=bool(checked)))
        row.addWidget(self._fill_all_layers)
        row.addStretch(1)
        return widget

    def _build_selection_strip(self, lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_select_mode", "Mode:")))
        self._select_mode = QComboBox()
        for mode, (key, fallback) in zip(SELECTION_MODES, (
            ("paint_select_replace", "Replace"),
            ("paint_select_add", "Add"),
            ("paint_select_subtract", "Subtract"),
            ("paint_select_intersect", "Intersect"),
        ), strict=True):
            self._select_mode.addItem(lang.get(key, fallback), mode)
        self._select_mode.setToolTip(lang.get(
            "paint_select_mode_tooltip",
            "How a new selection combines with the existing one",
        ))
        self._select_mode.currentIndexChanged.connect(self._on_select_mode)
        row.addWidget(self._select_mode)
        row.addStretch(1)
        return widget

    def _build_gradient_strip(self, lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_gradient_kind", "Kind:")))
        self._gradient_kind = QComboBox()
        for kind, (key, fallback) in zip(GRADIENT_KINDS, (
            ("paint_gradient_linear", "Linear"),
            ("paint_gradient_radial", "Radial"),
            ("paint_gradient_angle", "Angle"),
            ("paint_gradient_diamond", "Diamond"),
        ), strict=True):
            self._gradient_kind.addItem(lang.get(key, fallback), kind)
        self._gradient_kind.setToolTip(lang.get(
            "paint_gradient_kind_tooltip",
            "Gradient shape — drag from the FG end to the BG end on the canvas",
        ))
        self._gradient_kind.currentIndexChanged.connect(self._on_gradient_kind)
        row.addWidget(self._gradient_kind)
        self._gradient_reverse = QCheckBox(lang.get("paint_gradient_reverse", "Reverse"))
        self._gradient_reverse.setToolTip(lang.get(
            "paint_gradient_reverse_tooltip",
            "Swap the FG / BG ends of the gradient",
        ))
        self._gradient_reverse.toggled.connect(
            lambda checked: None if self._suspend else self._state.set_gradient(reverse=checked))
        row.addWidget(self._gradient_reverse)
        row.addStretch(1)
        return widget

    @staticmethod
    def _build_empty_strip(lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        hint = QLabel(lang.get(
            "paint_options_no_options",
            "(no options for this tool)",
        ))
        hint.setStyleSheet("color: #888;")
        row.addWidget(hint)
        row.addStretch(1)
        return widget

    # ---- state sync ------------------------------------------------------

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_TOOL:
            self.set_tool(self._state.tool)
        elif channel == ts.EVENT_BRUSH:
            self._refresh_brush_strip()
        elif channel in (ts.EVENT_FILL, ts.EVENT_SELECTION_MODE, ts.EVENT_GRADIENT):
            self._refresh_option_strips()

    def _refresh_option_strips(self) -> None:
        """Show the fill, selection and gradient settings the state holds."""
        self._suspend = True
        try:
            fill = self._state.fill
            self._fill_tolerance.setValue(fill.tolerance)
            self._fill_contiguous.setChecked(fill.contiguous)
            self._fill_all_layers.setChecked(fill.sample_all_layers)
            self._select_mode.setCurrentIndex(self._select_mode.findData(self._state.selection_mode))
            self._gradient_kind.setCurrentIndex(self._gradient_kind.findData(self._state.gradient_kind))
            self._gradient_reverse.setChecked(self._state.gradient_reverse)
        finally:
            self._suspend = False

    def _set_fill(self, **values) -> None:
        if not self._suspend:
            self._state.set_fill(**values)

    def _on_select_mode(self, index: int) -> None:
        if not self._suspend and index >= 0:
            self._state.set_selection_mode(self._select_mode.itemData(index))

    def _on_gradient_kind(self, index: int) -> None:
        if not self._suspend and index >= 0:
            self._state.set_gradient(kind=self._gradient_kind.itemData(index))

    def _refresh_brush_strip(self) -> None:
        self._suspend = True
        try:
            self._brush_size.setValue(self._state.brush.size)
            self._brush_opacity.setValue(int(round(self._state.brush.opacity * 100)))
            self._brush_hardness.setValue(int(round(self._state.brush.hardness * 100)))
        finally:
            self._suspend = False

    def _on_brush_size(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(size=int(self._brush_size.value()))

    def _on_brush_opacity(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(opacity=self._brush_opacity.value() / 100.0)

    def _on_brush_hardness(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(hardness=self._brush_hardness.value() / 100.0)


def _slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    s.setFixedWidth(120)
    return s
