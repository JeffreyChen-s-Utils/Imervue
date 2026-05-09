"""MediBang-style tool bars for the Paint workspace.

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

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


# ---------------------------------------------------------------------------
# Tool ordering — the left bar walks this list in order so additions slot in
# without breaking layout. Separators are inserted at the documented
# breakpoints to mirror MediBang's visual grouping.
# ---------------------------------------------------------------------------
TOOL_ORDER = (
    ("brush",         "B"),
    ("eraser",        "E"),
    ("fill",          "F"),
    ("eyedropper",    "I"),
    None,             # ── group break
    ("select_rect",   "M"),
    ("select_lasso",  "L"),
    ("select_wand",   "W"),
    ("select_quick",  "Q"),
    ("move",          "V"),
    None,             # ── group break
    ("text",          "T"),
    ("gradient",      "G"),
    ("blur",          ""),
    ("smudge",        ""),
    ("bezier_pen",    "P"),
    ("clone_stamp",   "S"),
    ("speech_bubble", "Ctrl+B"),
    ("shape_rect",    "Shift+R"),
    ("shape_ellipse", "Shift+E"),
    ("shape_line",    "Shift+I"),
    ("shape_polygon", "Shift+P"),
    ("crop",          "C"),
    ("transform",     "Ctrl+T"),
    None,             # ── group break
    ("hand",          "H"),
    ("zoom",          "Z"),
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
            tool, shortcut = entry
            self._add_tool_action(tool, shortcut, lang)

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

    # ---- internals -------------------------------------------------------

    def _add_tool_action(self, tool: str, shortcut: str, lang: dict) -> None:
        label = lang.get(f"paint_tool_{tool}", tool.replace("_", " ").title())
        action = QAction(label, self)
        action.setCheckable(True)
        action.setActionGroup(self._group)
        if shortcut:
            action.setShortcut(shortcut)
            action.setToolTip(f"{label} ({shortcut})")
        else:
            action.setToolTip(label)
        action.triggered.connect(lambda checked=False, t=tool: self._on_tool_clicked(t))
        self.addAction(action)
        self._actions[tool] = action

    def _on_tool_clicked(self, tool: str) -> None:
        if self._state.set_tool(tool):
            self.tool_picked.emit(tool)

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_TOOL:
            self.set_active_tool(self._state.tool)


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
        for tool in ("select_rect", "select_lasso", "select_wand"):
            self._page_for_tool[tool] = select_idx

        # Text — font / size / bold / italic
        text_idx = self._stack.addWidget(self._build_text_strip(lang))
        self._page_for_tool["text"] = text_idx

        # Gradient — preset combo
        gradient_idx = self._stack.addWidget(self._build_gradient_strip(lang))
        self._page_for_tool["gradient"] = gradient_idx

        # Empty page for tools with no options yet (move / hand / zoom / blur / smudge / eyedropper)
        empty_idx = self._stack.addWidget(self._build_empty_strip(lang))
        for tool in (
            "eyedropper", "move", "hand", "zoom", "blur", "smudge",
            "bezier_pen", "clone_stamp", "transform", "speech_bubble",
            "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
            "crop",
        ):
            self._page_for_tool[tool] = empty_idx

        self.addWidget(self._stack)
        self.set_tool(state.tool)
        self._refresh_brush_strip()

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

    @staticmethod
    def _build_fill_strip(lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_fill_tolerance", "Tolerance:")))
        tol = _slider(0, 255, 32)
        tol.setToolTip(lang.get(
            "paint_fill_tolerance_tooltip",
            "Per-channel colour distance accepted as the same region (0 exact, 255 anything)",
        ))
        row.addWidget(tol)
        contiguous = QCheckBox(lang.get("paint_fill_contiguous", "Contiguous"))
        contiguous.setToolTip(lang.get(
            "paint_fill_contiguous_tooltip",
            "On: only pixels reachable from the click. Off: every matching pixel canvas-wide.",
        ))
        row.addWidget(contiguous)
        all_layers = QCheckBox(
            lang.get("paint_fill_all_layers", "Sample all layers"),
        )
        all_layers.setToolTip(lang.get(
            "paint_fill_all_layers_tooltip",
            "Use the visible composite for the colour match instead of just the active layer",
        ))
        row.addWidget(all_layers)
        row.addStretch(1)
        return widget

    @staticmethod
    def _build_selection_strip(lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_select_mode", "Mode:")))
        mode = QComboBox()
        for key, fallback in (
            ("paint_select_replace", "Replace"),
            ("paint_select_add", "Add"),
            ("paint_select_subtract", "Subtract"),
            ("paint_select_intersect", "Intersect"),
        ):
            mode.addItem(lang.get(key, fallback))
        mode.setToolTip(lang.get(
            "paint_select_mode_tooltip",
            "How a new selection combines with the existing one",
        ))
        row.addWidget(mode)
        row.addWidget(QLabel(lang.get("paint_select_feather", "Feather:")))
        feather = _slider(0, 100, 0)
        feather.setToolTip(lang.get(
            "paint_select_feather_tooltip",
            "Soften the selection edge (px)",
        ))
        row.addWidget(feather)
        row.addStretch(1)
        return widget

    @staticmethod
    def _build_text_strip(lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_text_font", "Font:")))
        from PySide6.QtWidgets import QFontComboBox
        font_box = QFontComboBox()
        font_box.setToolTip(lang.get(
            "paint_text_font_tooltip",
            "Typeface used for new text layers",
        ))
        row.addWidget(font_box)
        row.addWidget(QLabel(lang.get("paint_text_size", "Size:")))
        size = QSpinBox()
        size.setRange(6, 400)
        size.setValue(36)
        size.setToolTip(lang.get(
            "paint_text_size_tooltip",
            "Type size in points",
        ))
        row.addWidget(size)
        bold = QCheckBox(lang.get("paint_text_bold", "Bold"))
        bold.setToolTip(lang.get(
            "paint_text_bold_tooltip", "Bold weight",
        ))
        row.addWidget(bold)
        italic = QCheckBox(lang.get("paint_text_italic", "Italic"))
        italic.setToolTip(lang.get(
            "paint_text_italic_tooltip", "Italic style",
        ))
        row.addWidget(italic)
        row.addStretch(1)
        return widget

    @staticmethod
    def _build_gradient_strip(lang: dict) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(6, 0, 6, 0)
        row.addWidget(QLabel(lang.get("paint_gradient_kind", "Kind:")))
        kind = QComboBox()
        for key, fallback in (
            ("paint_gradient_linear", "Linear"),
            ("paint_gradient_radial", "Radial"),
            ("paint_gradient_angle", "Angle"),
            ("paint_gradient_diamond", "Diamond"),
        ):
            kind.addItem(lang.get(key, fallback))
        kind.setToolTip(lang.get(
            "paint_gradient_kind_tooltip",
            "Gradient shape — drag from the FG end to the BG end on the canvas",
        ))
        row.addWidget(kind)
        reverse = QCheckBox(lang.get("paint_gradient_reverse", "Reverse"))
        reverse.setToolTip(lang.get(
            "paint_gradient_reverse_tooltip",
            "Swap the FG / BG ends of the gradient",
        ))
        row.addWidget(reverse)
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
