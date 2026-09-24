"""
Annotation dialog — macOS Preview Markup style image annotation.

Opens on a PIL image (from disk or the clipboard) and lets the user draw
rectangles, ellipses, lines, arrows, freehand strokes, text, mosaic, and
blur annotations on top. Save writes a flattened PNG/JPEG (destructive);
Save Project writes the annotations as JSON so they can be reloaded and
re-edited without losing layer information.

Layout
------
    +----------------------------------------------------+
    | [tool buttons] | [color] [width] | [undo] [redo]   |  <- QToolBar
    +----------------------------------------------------+
    |                                                    |
    |                 AnnotationCanvas                   |
    |                                                    |
    +----------------------------------------------------+
    |       [Project...] [Copy] [Save As] [Save]         |  <- bottom bar
    +----------------------------------------------------+
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from collections.abc import Callable

from PIL import Image
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (
    QAction, QColor, QFont, QKeySequence, QUndoStack,
)
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QMenu, QMenuBar, QSizePolicy,
    QStatusBar, QToolButton, QVBoxLayout, QWidget,
    QWidgetAction,
)

from Imervue.gui.annotation_canvas import (
    _MODE_RGBA,
    AnnotationCanvas,
    _AddAnnotationCommand,
    _DeleteAnnotationCommand,
    _ModifyAnnotationCommand,
    _point_segment_distance,
)
from Imervue.gui.annotation_destructive import _BakeDestructiveCommand
from Imervue.image.orientation import exif_orientation, transpose_for
from Imervue.gui.annotation_file_actions import (
    _LOAD_PROJECT_FALLBACK,
    AnnotationFileActionsMixin,
)
from Imervue.gui.slider_spin import make_slider_spin
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.qimage_convert import pil_to_qimage, qimage_to_pil
from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue.annotation")

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# The annotation canvas and its undo commands live in ``annotation_canvas`` and
# the PIL<->QImage helpers in ``system.qimage_convert``; these names are
# re-exported here so existing
# ``from annotation_dialog import AnnotationCanvas / _AddAnnotationCommand /
# pil_to_qimage`` call sites and tests keep working unchanged.
__all__ = [
    "AnnotationCanvas",
    "AnnotationDialog",
    "AnnotationEditorWidget",
    "_AddAnnotationCommand",
    "_BakeDestructiveCommand",
    "_DeleteAnnotationCommand",
    "_ModifyAnnotationCommand",
    "_point_segment_distance",
    "open_annotation_for_clipboard_image",
    "open_annotation_for_path",
    "pil_to_qimage",
    "qimage_to_pil",
]

# Dialog-only UI constants (the canvas owns the drawing constants).
_QSS_PANEL_SECTION = "panelSection"

# ---------------------------------------------------------------------------
# Editor widget — reusable QWidget form of the annotation editor.
#
# The same widget is hosted inside the legacy ``AnnotationDialog`` (for the
# clipboard-capture / "open in modal" flow) and can also be dropped into a
# tab / dock panel / any other QWidget container so the full editor —
# menubar, toolbox, canvas, brushes, Modify actions — lives right next to
# the main viewer instead of a separate top-level window.
# ---------------------------------------------------------------------------

# Dark panel styling for the editor's toolbox, right panel and canvas surround. Scoped to
# those object names so it doesn't fight the application theme elsewhere.
_EDITOR_STYLE_SHEET = """
QFrame#annotationCanvasFrame {
    background-color: #1e1e1e;
}
QFrame#annotationLeftToolbox,
QFrame#annotationRightPanel {
    background-color: #2d2d30;
    color: #e0e0e0;
    border-right: 1px solid #3f3f42;
}
QFrame#annotationRightPanel {
    border-right: none;
    border-left: 1px solid #3f3f42;
}
QFrame#annotationLeftToolbox QToolButton,
QFrame#annotationRightPanel QToolButton {
    background-color: #3c3c3c;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 2px;
}
QFrame#annotationLeftToolbox QToolButton:hover,
QFrame#annotationRightPanel QToolButton:hover {
    background-color: #4a4a4a;
}
QFrame#annotationLeftToolbox QToolButton:checked {
    background-color: #0a6cbc;
    border: 1px solid #3e95d6;
}
QFrame#annotationRightPanel QLabel {
    color: #e0e0e0;
}
QFrame#annotationRightPanel QLabel#panelSection {
    color: #9cdcfe;
    font-weight: bold;
    padding-top: 6px;
}
QFrame#annotationRightPanel QSpinBox,
QFrame#annotationRightPanel QSlider {
    background-color: #3c3c3c;
    color: #e0e0e0;
}
"""

class AnnotationEditorWidget(AnnotationFileActionsMixin, QWidget):
    """Professional-editor QWidget: menubar + toolbox + canvas + right panel.

    Parameters
    ----------
    base:
        The PIL image the editor opens on.
    source_path:
        Path of ``base`` on disk, or ``""`` for in-memory (clipboard) images.
    on_saved:
        Optional callback fired after a successful save to ``source_path``.
    modify_target:
        Optional ``GPUImageView`` — when provided, the editor's menu bar
        grows a "Modify" menu embedding :class:`ModifyActionsWidget`, so
        Develop / Rotate / Flip / Reset are reachable from the editor too.
    parent:
        Usual Qt parent.
    """

    # Fired when the File → Close menu entry is triggered. Host containers
    # decide what "close" means — the legacy dialog connects it to
    # ``QDialog.accept``; a tab host can tear the tab down instead.
    close_requested = Signal()

    def __init__(
        self,
        base: Image.Image,
        source_path: str = "",
        on_saved: Callable[[str], None] | None = None,
        modify_target: GPUImageView | None = None,
        parent=None,
        default_tool: str = "",
    ):
        super().__init__(parent)
        self._source_path = source_path
        self._default_tool = default_tool
        # Optional callback fired after a successful destructive save —
        # used by ``open_annotation_for_path`` to refresh the main viewer.
        self._on_saved = on_saved
        self._modify_target = modify_target

        self._undo_stack = QUndoStack(self)
        self._canvas = AnnotationCanvas(base, self._undo_stack, self)

        # ---------- Root layout ----------
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1) 上方 menu bar — QDialog 沒有原生 menuBar()，但 QVBoxLayout
        # 可透過 setMenuBar 把 QMenuBar 塞到頂端，效果與 QMainWindow 相同。
        self._menu_bar = self._build_menu_bar()
        root.setMenuBar(self._menu_bar)

        # 2) 中段主要內容：左工具箱 / 中央 canvas / 右屬性面板。
        root.addLayout(self._build_body(), 1)

        # 3) 底部狀態列 — 顯示當前工具 / 座標 / 影像尺寸。
        self._status_bar = self._build_status_bar()
        root.addWidget(self._status_bar)

        # ---------- Style ----------
        # 不強制黑底（會跟使用者整體 theme 打架），只對幾個關鍵區塊加背景色
        # 與邊框，讓它看起來有 "多面板編輯器" 的分區感。
        self.setStyleSheet(_EDITOR_STYLE_SHEET)

        # Connect canvas signals to status bar / property panel updates.
        self._canvas.cursor_image_pos.connect(self._on_cursor_moved)
        self._canvas.tool_changed.connect(self._on_canvas_tool_changed)

        self._install_shortcuts()
        self._refresh_status_bar()

        # Apply default tool if requested (e.g. open directly to mosaic/blur)
        if self._default_tool:
            self._canvas.set_tool(self._default_tool)

    def _build_body(self) -> QHBoxLayout:
        """Left toolbox, the framed canvas (stretching) and the right properties panel."""
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._left_toolbox = self._build_left_toolbox()
        body.addWidget(self._left_toolbox)
        body.addWidget(self._build_canvas_frame(), 1)
        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel)
        return body

    def _build_canvas_frame(self) -> QFrame:
        """Dark surround for the canvas.

        Canvas 外面再包一層 QFrame 做暗色背景，模擬 Photoshop / external image editors
        在 canvas 四周的 "workspace" 深灰空間感。
        """
        canvas_frame = QFrame(self)
        canvas_frame.setObjectName("annotationCanvasFrame")
        canvas_frame.setFrameShape(QFrame.Shape.NoFrame)
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self._canvas, 1)
        return canvas_frame

    # ========================================================================
    # Professional editor layout — menubar / left toolbox / right panel /
    # status bar. Designed to look like Photoshop / external image editors / : narrow
    # vertical tool column on the left, dockable-looking properties on the
    # right, dark workspace around the canvas, status bar with live readouts.
    # ========================================================================

    # Left toolbox button size — compact, single-column stack. Label still
    # visible so every tool announces itself without relying on tooltips.
    _TOOL_BTN_SIZE = QSize(86, 66)
    _TOOL_BTN_LABEL_POINT = 9
    _LEFT_TOOLBOX_WIDTH = 102
    _RIGHT_PANEL_WIDTH = 248

    # Compact-tool list used by both the toolbox and the keyboard shortcuts.
    # Definition order is the visual stacking order in the left column.
    def _tool_definitions(self) -> list[tuple[str, str, str]]:
        lang = language_wrapper.language_word_dict
        return [
            ("select",   "⬚", lang.get("annotation_tool_select", "Select")),
            ("rect",     "▢", lang.get("annotation_tool_rect", "Rectangle")),
            ("ellipse",  "◯", lang.get("annotation_tool_ellipse", "Ellipse")),
            ("line",     "╱", lang.get("annotation_tool_line", "Line")),
            ("arrow",    "→", lang.get("annotation_tool_arrow", "Arrow")),
            ("freehand", "✎", lang.get("annotation_tool_freehand", "Freehand")),
            ("text",     "T", lang.get("annotation_tool_text", "Text")),
            ("mosaic",   "▦", lang.get("annotation_tool_mosaic", "Mosaic")),
            ("blur",     "◌", lang.get("annotation_tool_blur", "Blur")),
        ]

    def _make_compact_tool_button(self, glyph: str, label: str) -> QToolButton:
        """Small QToolButton with glyph above label — suited for the left
        vertical toolbox. Labels stay visible (per earlier user feedback)
        but the footprint is much tighter than the old 120×96 toolbar.
        """
        btn = QToolButton(self)
        btn.setText(f"{glyph}\n{label}")
        btn.setToolTip(label)
        font = QFont(btn.font())
        font.setPointSize(self._TOOL_BTN_LABEL_POINT)
        btn.setFont(font)
        btn.setFixedSize(self._TOOL_BTN_SIZE)
        return btn

    # ---------- Menu bar ----------

    def _build_menu_bar(self) -> QMenuBar:
        """File / Edit menu bar, raster-editor.

        Actions previously living in the bottom button row (Save, Save As,
        Copy, Save Project, Load Project) are moved here; Edit holds
        Undo / Redo / Delete Selection. Every action has a keyboard
        shortcut attached so power users don't need the menu at all.
        """
        lang = language_wrapper.language_word_dict
        mb = QMenuBar(self)
        self._add_file_menu(mb, lang)
        self._add_edit_menu(mb, lang)
        self._add_modify_menu(mb, lang)
        return mb

    def _menu_action(self, menu: QMenu, text: str, slot, shortcut=None) -> QAction:
        """Add an editor-owned action to ``menu``, wired to ``slot``, with an optional shortcut."""
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _add_file_menu(self, mb: QMenuBar, lang) -> None:
        """Save / Save As / Copy, project save and load, then Close."""
        file_menu = mb.addMenu(lang.get("annotation_menu_file", "File"))
        self._menu_action(file_menu, lang.get("annotation_save", "Save"), self._save, "Ctrl+S")
        self._menu_action(file_menu, lang.get("annotation_save_as", "Save As..."),
                          self._save_as, "Ctrl+Shift+S")
        self._menu_action(file_menu, lang.get("annotation_copy_clipboard", "Copy to Clipboard"),
                          self._copy_to_clipboard, "Ctrl+C")
        file_menu.addSeparator()
        self._menu_action(file_menu, lang.get("annotation_save_project", "Save Project..."),
                          self._save_project)
        self._menu_action(file_menu, lang.get("annotation_load_project", _LOAD_PROJECT_FALLBACK),
                          self._load_project)
        file_menu.addSeparator()
        # Emit a signal instead of calling ``self.close``: the editor widget
        # may be embedded in a dialog, tab, or dock — each host decides what
        # "close" means (dialog.accept, tab removal, panel hide, ...).
        self._menu_action(file_menu, lang.get("annotation_menu_close", "Close"),
                          self.close_requested.emit, "Ctrl+W")

    def _add_edit_menu(self, mb: QMenuBar, lang) -> None:
        """Undo / Redo bound to the editor's undo stack, then Delete Selection."""
        edit_menu = mb.addMenu(lang.get("annotation_menu_edit", "Edit"))

        act_undo = self._undo_stack.createUndoAction(
            self, lang.get("annotation_undo", "Undo")
        )
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(act_undo)

        act_redo = self._undo_stack.createRedoAction(
            self, lang.get("annotation_redo", "Redo")
        )
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(act_redo)

        edit_menu.addSeparator()
        self._menu_action(
            edit_menu, lang.get("annotation_menu_delete_selection", "Delete Selection"),
            self._delete_selected, Qt.Key.Key_Delete)

    def _add_modify_menu(self, mb: QMenuBar, lang) -> None:
        """Develop / Rotate / Flip / Reset for the main viewer's image.

        Only built when a ``modify_target`` (GPUImageView) was supplied,
        because these operate on the main viewer's current image, not on the
        in-editor PIL copy. Tests and the clipboard-capture flow don't pass a
        target, so the menu is simply absent there.
        """
        if self._modify_target is None:
            return
        from Imervue.gui.modify_actions_widget import ModifyActionsWidget

        modify_menu = mb.addMenu(lang.get("modify_menu_title", "Modify"))
        modify_widget_action = QWidgetAction(modify_menu)
        modify_widget = ModifyActionsWidget(
            main_gui=self._modify_target,
            parent=modify_menu,
            on_triggered=modify_menu.close,
        )
        modify_widget_action.setDefaultWidget(modify_widget)
        modify_menu.addAction(modify_widget_action)

    # ---------- Left toolbox ----------

    def _build_left_toolbox(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("annotationLeftToolbox")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setFixedWidth(self._LEFT_TOOLBOX_WIDTH)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(4)

        lang = language_wrapper.language_word_dict
        header = QLabel(lang.get("annotation_tools_section", "Tools"), frame)
        header.setObjectName(_QSS_PANEL_SECTION)
        header.setStyleSheet(
            "color: #9cdcfe; font-weight: bold; padding-bottom: 4px;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(header)

        self._tool_buttons: dict[str, QToolButton] = {}
        for tool, glyph, label in self._tool_definitions():
            btn = self._make_compact_tool_button(glyph, label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, t=tool: self._on_tool_selected(t))
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._tool_buttons[tool] = btn
        self._tool_buttons["select"].setChecked(True)

        lay.addStretch(1)
        return frame

    # ---------- Right properties panel ----------

    @staticmethod
    def _section_label(frame: QFrame, text: str) -> QLabel:
        """A right-panel section heading, styled through ``_QSS_PANEL_SECTION``."""
        label = QLabel(text, frame)
        label.setObjectName(_QSS_PANEL_SECTION)
        return label

    def _on_stroke_width_changed(self, width: int) -> None:
        self._canvas.set_stroke_width(width)
        self._refresh_status_bar()

    @staticmethod
    def _wide_button(frame: QFrame, text: str, height: int) -> QToolButton:
        """A tool button that stretches across its row at a fixed height."""
        btn = QToolButton(frame)
        btn.setText(text)
        btn.setFixedHeight(height)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return btn

    def _build_right_panel(self) -> QFrame:
        lang = language_wrapper.language_word_dict
        frame = QFrame(self)
        frame.setObjectName("annotationRightPanel")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setFixedWidth(self._RIGHT_PANEL_WIDTH)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        self._add_panel_header(frame, lay, lang)
        lay.addSpacing(6)

        # ---- Color section ----
        lay.addWidget(self._section_label(
            frame, lang.get("annotation_color", "Color")))
        lay.addWidget(self._build_color_button(frame, lang))
        lay.addSpacing(4)

        # ---- Stroke width section ----
        lay.addWidget(self._section_label(
            frame, lang.get("annotation_stroke_width_label", "Stroke Width")))
        self._width_slider, self._width_spin, sw_row = make_slider_spin(
            frame, 1, 40, 3, on_change=self._on_stroke_width_changed)
        lay.addLayout(sw_row)
        lay.addSpacing(8)

        # ---- History quick actions (Undo / Redo) ----
        lay.addWidget(self._section_label(
            frame, lang.get("annotation_history_section", "History")))
        lay.addLayout(self._build_history_row(frame, lang))
        lay.addSpacing(8)

        # ---- Brush section (freehand only) ----
        lay.addWidget(self._section_label(
            frame, lang.get("annotation_brush_section", "Brush")))
        lay.addLayout(self._build_brush_grid(frame, lang))
        lay.addSpacing(4)

        # Opacity slider + spin
        lay.addWidget(self._section_label(
            frame, lang.get("annotation_opacity", "Opacity")))
        self._opacity_slider, self._opacity_spin, op_row = make_slider_spin(
            frame, 0, 100, 100, suffix=" %",
            on_change=lambda v: self._canvas.set_brush_opacity(v))
        lay.addLayout(op_row)
        lay.addSpacing(4)

        # Spacing slider + spin (spray only, but always visible for clarity)
        lay.addWidget(self._section_label(
            frame, lang.get("annotation_spacing", "Spacing")))
        self._spacing_slider, self._spacing_spin, sp_row = make_slider_spin(
            frame, 1, 40, 8,
            on_change=lambda v: self._canvas.set_brush_spacing(v))
        lay.addLayout(sp_row)

        lay.addStretch(1)
        return frame

    def _add_panel_header(self, frame: QFrame, lay: QVBoxLayout, lang) -> None:
        """Bold "Properties" title and the current-tool readout under it."""
        title = QLabel(lang.get("annotation_properties", "Properties"), frame)
        title_font = QFont(title.font())
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        lay.addWidget(title)

        # Current tool readout — big and obvious, mirrors Photoshop's
        # tool-options strip where the active tool name is always visible.
        self._current_tool_label = QLabel("", frame)
        ct_font = QFont(self._current_tool_label.font())
        ct_font.setPointSize(10)
        self._current_tool_label.setFont(ct_font)
        self._current_tool_label.setStyleSheet("color: #cccccc;")
        lay.addWidget(self._current_tool_label)

    def _build_color_button(self, frame: QFrame, lang) -> QToolButton:
        """Swatch button showing the stroke colour; clicking opens the picker."""
        self._color = (255, 0, 0, 255)
        self._color_btn = self._wide_button(
            frame, lang.get("annotation_color", "Color"), 44)
        self._color_btn.setAutoRaise(False)
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_button_style()
        return self._color_btn

    def _build_history_row(self, frame: QFrame, lang) -> QHBoxLayout:
        """Undo / Redo buttons bound to the dialog's undo stack."""
        hist_row = QHBoxLayout()
        hist_row.setContentsMargins(0, 0, 0, 0)
        hist_row.setSpacing(6)

        undo_btn = self._wide_button(
            frame, "↶ " + lang.get("annotation_undo", "Undo"), 36)
        undo_btn.clicked.connect(self._undo_stack.undo)
        hist_row.addWidget(undo_btn)

        redo_btn = self._wide_button(
            frame, "↷ " + lang.get("annotation_redo", "Redo"), 36)
        redo_btn.clicked.connect(self._undo_stack.redo)
        hist_row.addWidget(redo_btn)
        return hist_row

    def _build_brush_grid(self, frame: QFrame, lang) -> QGridLayout:
        """Two-column grid of exclusive brush buttons, Pen checked."""
        brush_grid = QGridLayout()
        brush_grid.setContentsMargins(0, 0, 0, 0)
        brush_grid.setSpacing(4)

        self._brush_buttons: dict[str, QToolButton] = {}
        self._brush_button_group = QButtonGroup(frame)
        self._brush_button_group.setExclusive(True)
        brush_defs: list[tuple[str, str, str]] = [
            ("pen",         "✒",  lang.get("annotation_brush_pen",         "Pen")),
            ("marker",      "🖊", lang.get("annotation_brush_marker",      "Marker")),
            ("pencil",      "✏",  lang.get("annotation_brush_pencil",      "Pencil")),
            ("highlighter", "🖍", lang.get("annotation_brush_highlighter", "Highlighter")),
            ("spray",       "💨", lang.get("annotation_brush_spray",       "Spray")),
        ]
        for idx, (key, glyph, label) in enumerate(brush_defs):
            btn = self._wide_button(frame, f"{glyph} {label}", 30)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, k=key: self._on_brush_selected(k))
            row, col = divmod(idx, 2)
            brush_grid.addWidget(btn, row, col)
            self._brush_buttons[key] = btn
            self._brush_button_group.addButton(btn)
        self._brush_buttons["pen"].setChecked(True)
        return brush_grid

    def _on_brush_selected(self, brush: str) -> None:
        if brush not in self._brush_buttons:
            return
        for key, btn in self._brush_buttons.items():
            btn.setChecked(key == brush)
        self._canvas.set_brush_type(brush)

    # ---------- Status bar ----------

    def _build_status_bar(self) -> QStatusBar:
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(False)
        bar.setStyleSheet(
            "QStatusBar { background-color: #007acc; color: white; }"
            "QStatusBar QLabel { color: white; padding: 0 8px; }"
        )

        self._status_tool_label = QLabel("", bar)
        self._status_pos_label = QLabel("", bar)
        self._status_size_label = QLabel("", bar)

        bar.addWidget(self._status_tool_label, 1)
        bar.addPermanentWidget(self._status_pos_label)
        bar.addPermanentWidget(self._status_size_label)
        return bar

    # ---------- Status / panel refresh helpers ----------

    def _tool_display_label(self, tool: str) -> str:
        for key, _glyph, label in self._tool_definitions():
            if key == tool:
                return label
        return tool

    def _refresh_status_bar(self) -> None:
        lang = language_wrapper.language_word_dict
        tool_label = self._tool_display_label(self._canvas.current_tool())
        self._status_tool_label.setText(
            f"{lang.get('annotation_status_tool', 'Tool')}: {tool_label}"
        )
        base = self._canvas.get_base_pil()
        self._status_size_label.setText(
            f"{lang.get('annotation_status_size', 'Size')}: "
            f"{base.width} × {base.height}"
        )
        if self._current_tool_label is not None:
            self._current_tool_label.setText(
                f"{lang.get('annotation_current_tool', 'Current Tool')}: "
                f"{tool_label}"
            )

    def _on_cursor_moved(self, ix: int, iy: int) -> None:
        lang = language_wrapper.language_word_dict
        self._status_pos_label.setText(
            f"{lang.get('annotation_status_pos', 'Pos')}: "
            f"{ix}, {iy}"
        )

    def _on_canvas_tool_changed(self, tool: str) -> None:
        # Keep the toolbox highlight in sync with set_tool calls that
        # originate from keyboard shortcuts rather than button clicks.
        for name, btn in self._tool_buttons.items():
            btn.setChecked(name == tool)
        self._refresh_status_bar()

    def _delete_selected(self) -> None:
        """Edit → Delete Selection — forwards to the canvas's delete path."""
        sel_id = self._canvas._selected_id
        if sel_id is None:
            return
        sel = self._canvas._find(sel_id)
        if sel is None:
            return
        cmd = _DeleteAnnotationCommand(self._canvas, sel)
        self._undo_stack.push(cmd)
        self._canvas.annotation_changed.emit()

    def _install_shortcuts(self) -> None:
        """Shortcuts that aren't already attached to a menu QAction.

        Save / Save As / Copy / Undo / Redo / Delete live on actions in
        the menu bar, so their QKeySequences fire automatically when the
        dialog has focus. This hook is reserved for anything that isn't
        menu-reachable — currently empty but kept so subclasses / future
        features have an obvious extension point.
        """
        pass

    # ---------- Toolbar handlers ----------

    def _on_tool_selected(self, tool: str) -> None:
        for name, btn in self._tool_buttons.items():
            btn.setChecked(name == tool)
        self._canvas.set_tool(tool)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(
            QColor(*self._color),
            self,
            language_wrapper.language_word_dict.get("annotation_color", "Color"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if c.isValid():
            self._color = (c.red(), c.green(), c.blue(), c.alpha())
            self._update_color_button_style()
            self._canvas.set_color(self._color)

    def _update_color_button_style(self) -> None:
        r, g, b, a = self._color
        text_color = "black" if (r + g + b) > 384 else "white"
        self._color_btn.setStyleSheet(
            f"QToolButton {{ background-color: rgba({r},{g},{b},{a}); "
            f"color: {text_color}; border: 1px solid #888; padding: 4px 10px; }}"
        )

    # ---------- Save / export ----------


# ---------------------------------------------------------------------------
# Legacy dialog wrapper
# ---------------------------------------------------------------------------

class AnnotationDialog(QDialog):
    """Thin ``QDialog`` wrapper hosting an :class:`AnnotationEditorWidget`.

    Kept so callers that want the editor as a modal window (clipboard
    capture, right-click menu) don't have to manage a top-level widget
    themselves. Any attribute access that isn't defined on the dialog
    falls through to the embedded editor — tests rely on poking
    ``dlg._canvas`` / ``dlg._baked_image()`` / ``dlg._write()`` / etc.
    directly, and that needs to keep working after the refactor.
    """

    def __init__(
        self,
        base: Image.Image,
        source_path: str = "",
        parent=None,
        on_saved: Callable[[str], None] | None = None,
        modify_target: GPUImageView | None = None,
        default_tool: str = "",
    ):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("annotation_title", "Annotate"))

        # 專業繪圖軟體風格的預設尺寸 — 超過螢幕時縮到 95%。
        default_w, default_h = 1280, 960
        screen = self.screen() if hasattr(self, "screen") else None
        if screen is None and parent is not None:
            screen = parent.screen() if hasattr(parent, "screen") else None
        if screen is not None:
            avail = screen.availableGeometry()
            default_w = min(default_w, int(avail.width() * 0.95))
            default_h = min(default_h, int(avail.height() * 0.95))
        self.resize(default_w, default_h)

        self._editor = AnnotationEditorWidget(
            base,
            source_path=source_path,
            on_saved=on_saved,
            modify_target=modify_target,
            parent=self,
            default_tool=default_tool,
        )
        # File → Close in the editor closes this hosting dialog.
        self._editor.close_requested.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._editor)

    def __getattr__(self, name: str):
        # ``__getattr__`` only fires when normal lookup fails, so dialog
        # attributes still take precedence. Everything else — canvas,
        # tool buttons, color state, save helpers — lives on the editor
        # widget and is forwarded transparently.
        if name.startswith("__"):
            raise AttributeError(name)
        editor = self.__dict__.get("_editor")
        if editor is None:
            raise AttributeError(name)
        return getattr(editor, name)


# ---------------------------------------------------------------------------
# Entry points (called from right-click menu / main window)
# ---------------------------------------------------------------------------

def open_annotation_for_path(
    main_gui: GPUImageView, path: str, default_tool: str = "",
) -> None:
    """Load ``path`` with PIL and open the annotation dialog on it.

    On a successful destructive save, refresh the main viewer so the
    annotated pixels appear immediately instead of the user having to
    click away and back.
    """
    try:
        img = Image.open(path)
        code = exif_orientation(img)
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert(_MODE_RGBA)
        else:
            img.load()  # force decode now so errors surface before the dialog
        # Upright, as the viewer shows it. The save writes no EXIF, so pixels
        # left sideways would lose their orientation tag and stay sideways.
        img = transpose_for(img, code)
    except Exception as exc:
        logger.exception("annotation load failed: %s", path)
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.error(f"Load failed: {exc}")
        return

    def _reload(saved_path: str) -> None:
        # Lazy import to avoid a top-level dependency on the viewer module
        # for the offline-testable parts of this file.
        from Imervue.gpu_image_view.images.image_loader import open_path
        with best_effort("clear the deep-zoom view before reopening", logger):
            main_gui._clear_deep_zoom()
        try:
            open_path(main_gui=main_gui, path=saved_path)
        except Exception:
            logger.exception("viewer reload after annotation save failed")

    dlg = AnnotationDialog(
        img,
        source_path=path,
        parent=main_gui.main_window,
        on_saved=_reload,
        modify_target=main_gui,
        default_tool=default_tool,
    )
    dlg.exec()


def open_annotation_for_clipboard_image(
    parent_window, img: Image.Image
) -> None:
    """Open the annotation dialog on a clipboard PIL image (no source path)."""
    dlg = AnnotationDialog(img, source_path="", parent=parent_window)
    dlg.exec()
