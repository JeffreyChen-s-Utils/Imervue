"""The Modify tab's tool palette and drawing-property handlers.

:class:`DevelopDrawingToolsMixin` builds the left two-column annotation tool
palette with its rotate / flip row onto the owning
:class:`~Imervue.gui.develop_panel.DevelopPanel`, tracks which tool is active,
drives the crop-ratio controls and forwards colour, brush and font changes
from the right panel to the live canvas.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog,
    QGridLayout,
    QScrollArea,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.ui_scale import scaled_px


class DevelopDrawingToolsMixin:
    """Tool palette, tool selection, crop ratio and drawing properties of :class:`DevelopPanel`."""

    # ------------------------------------------------------------------
    # Panel builders — called by ImervueMainWindow
    # ------------------------------------------------------------------

    def build_left_panel(self) -> QWidget:
        """Build the compact two-column tool palette and orientation controls."""
        lang = language_wrapper.language_word_dict

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        from Imervue.gui.tool_icons import tool_icon

        panel.setObjectName("modifyToolPalette")
        grid = QGridLayout()
        grid.setSpacing(scaled_px(4))
        layout.addLayout(grid)
        icons = {"select": "select_rect", "rect": "shape_rect", "ellipse": "shape_ellipse",
                 "line": "shape_line", "freehand": "brush"}
        # Two compact columns keep the image in focus, with accessible tool names.
        self._tool_buttons: dict[str, QToolButton] = {}
        for index, (tool_key, _glyph, i18n_key, fallback) in enumerate(self._ANNOTATION_TOOLS):
            btn = QToolButton()
            label = lang.get(i18n_key, fallback)
            btn.setText(label)
            btn.setAccessibleName(label)
            btn.setToolTip(label)
            btn.setIcon(tool_icon(icons.get(tool_key, tool_key)))
            btn.setIconSize(QSize(scaled_px(21), scaled_px(21)))
            btn.setProperty("paintTool", True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, t=tool_key: self._set_tool(t))
            grid.addWidget(btn, *divmod(index, 2))
            self._interactive_widgets.append(btn)
            self._tool_buttons[tool_key] = btn
        strip_buttons = list(self._tool_buttons.values())

        # Default: select tool checked
        if "select" in self._tool_buttons:
            self._tool_buttons["select"].setChecked(True)

        # Crop controls are built in build_right_panel() where there is
        # enough width for the combo box and buttons.

        # --- Separator ---
        layout.addSpacing(4)

        self._build_orientation_tools(layout, strip_buttons, lang)

        layout.addStretch(1)
        button_size = self._size_tool_buttons(strip_buttons)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        # Room for the buttons, the layout margins and a vertical scroll bar.
        bar = scroll.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        scroll.setMinimumWidth(
            2 * button_size.width() + scaled_px(12) + bar + 2 * scroll.frameWidth())
        scroll.setMinimumHeight(scaled_px(40))
        return scroll

    def _build_orientation_tools(self, layout, strip_buttons, lang):
        """Keep rotate and flip actions together below the drawing tools."""
        from Imervue.gui.tool_icons import tool_icon
        orient_buttons: list[tuple[str, str, str, Callable]] = [
            ("⟲", "develop_rotate_ccw", "Rotate 90° CCW", lambda: self._rotate(-1)),
            ("⟳", "develop_rotate_cw",  "Rotate 90° CW",  lambda: self._rotate(1)),
            ("⇆", "develop_flip_h",     "Flip Horizontal", self._flip_h),
            ("⇅", "develop_flip_v",     "Flip Vertical",   self._flip_v),
        ]
        orientation = QGridLayout()
        orientation.setSpacing(scaled_px(4))
        layout.addLayout(orientation)
        for index, (_glyph, i18n_key, fallback, handler) in enumerate(orient_buttons):
            btn = QToolButton()
            label = lang.get(i18n_key, fallback)
            btn.setText(label)
            btn.setAccessibleName(label)
            btn.setToolTip(label)
            btn.setIcon(tool_icon(("rotate_ccw", "rotate_cw", "flip_h", "flip_v")[index]))
            btn.setIconSize(QSize(scaled_px(21), scaled_px(21)))
            btn.setProperty("paintTool", True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.clicked.connect(handler)
            orientation.addWidget(btn, *divmod(index, 2))
            self._interactive_widgets.append(btn)
            strip_buttons.append(btn)

    @classmethod
    def _size_tool_buttons(cls, buttons: list[QToolButton]) -> QSize:
        """Size icon buttons consistently with the UI scale and native style hints."""
        size = QSize(scaled_px(cls._TOOL_BTN_SIZE.width()), scaled_px(cls._TOOL_BTN_SIZE.height()))
        for btn in buttons:
            size = size.expandedTo(btn.sizeHint())
        for btn in buttons:
            btn.setFixedSize(size)
        return size

    # ------------------------------------------------------------------
    # Left-panel tool selection
    # ------------------------------------------------------------------

    def _current_tool(self) -> str:
        """The annotation tool whose button is checked (default ``select``)."""
        for key, btn in self._tool_buttons.items():
            if btn.isChecked():
                return key
        return "select"

    def _set_tool(self, tool: str) -> None:
        if tool not in ("select", "crop"):
            self._property_tabs.setCurrentIndex(1)
        # Update button checked state
        for key, btn in self._tool_buttons.items():
            btn.setChecked(key == tool)
        # Show/hide crop controls
        self._crop_widget.setVisible(tool == "crop")
        if tool != "crop" and self._canvas is not None:
            self._canvas.clear_crop()
        if self._canvas is not None:
            self._canvas.set_tool(tool)
            if tool == "crop":
                rw, rh = self._crop_ratio_combo.currentData() or (0, 0)
                self._canvas.set_crop_ratio(rw, rh)

    def _on_crop_ratio_changed(self, _index: int) -> None:
        rw, rh = self._crop_ratio_combo.currentData() or (0, 0)
        if self._canvas is not None:
            self._canvas.set_crop_ratio(rw, rh)

    def _cancel_crop(self) -> None:
        if self._canvas is not None:
            self._canvas.clear_crop()
        self._set_tool("select")

    # ------------------------------------------------------------------
    # Right-panel drawing controls
    # ------------------------------------------------------------------

    def _pick_color(self) -> None:
        r, g, b, a = self._draw_color
        color = QColorDialog.getColor(
            QColor(r, g, b, a),
            self,
            language_wrapper.language_word_dict.get("annotation_color", "Color"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self._draw_color = (color.red(), color.green(), color.blue(), color.alpha())
            self._update_color_button_style()
            if self._canvas is not None:
                self._canvas.set_color(self._draw_color)

    def _update_color_button_style(self) -> None:
        r, g, b, a = self._draw_color
        self._color_btn.setStyleSheet(
            f"QToolButton {{ background-color: rgba({r},{g},{b},{a}); "
            f"color: {'#000' if (r + g + b) > 384 else '#fff'}; "
            f"border: 1px solid #555; border-radius: 3px; }}"
        )

    def _on_brush_selected(self, key: str) -> None:
        if self._canvas is not None:
            self._canvas.set_brush_type(key)

    def _on_font_changed(self, font: QFont) -> None:
        if self._canvas is not None:
            self._canvas.set_font_family(font.family())

    def _on_font_size_changed(self, v: int) -> None:
        if self._canvas is not None:
            self._canvas.set_font_size(v)
