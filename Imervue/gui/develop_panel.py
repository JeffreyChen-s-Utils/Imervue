"""Modify panel — inline annotation + non-destructive image adjustments.

A QWidget that provides ``build_left_panel()``, ``build_right_panel()``,
and an inline ``AnnotationCanvas`` to populate the Modify tab's
three-column layout:

    left tool strip | annotation canvas | right properties

- **Left panel**: annotation tool buttons (select, shapes, freehand,
  text, mosaic, blur) + orientation (rotate/flip)
- **Center**: an ``AnnotationCanvas`` showing the current image —
  drawing happens directly here, no dialog needed.
- **Right panel**: drawing properties (color, stroke width, brush,
  opacity, spacing), annotation undo/redo + save, develop sliders
  (exposure/brightness/contrast/saturation), recipe reset/undo/redo.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Callable

import numpy as np
from PIL import Image
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QUndoStack
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QFontComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView
    from Imervue.gui.annotation_dialog import AnnotationCanvas

logger = logging.getLogger("Imervue.develop_panel")


class DevelopPanel(QWidget):
    """Controller that builds the left/right panels for the Modify tab.

    Emits ``recipe_committed(path, old_recipe, new_recipe)`` whenever a
    develop-slider change is finalised (after the debounce timer fires).
    """

    recipe_committed = Signal(str, object, object)

    _COLOR_RANGE = 100
    _EXPOSURE_RANGE = 200
    _DEBOUNCE_MS = 200

    # Advanced develop sliders: (recipe_field, i18n_key, fallback_label)
    _ADVANCED_SLIDERS = [
        ("temperature", "develop_temperature", "Temperature"),
        ("tint",        "develop_tint",        "Tint"),
        ("highlights",  "develop_highlights",  "Highlights"),
        ("shadows",     "develop_shadows",     "Shadows"),
        ("whites",      "develop_whites",      "Whites"),
        ("blacks",      "develop_blacks",      "Blacks"),
        ("vibrance",    "develop_vibrance",    "Vibrance"),
    ]

    # Annotation tool definitions: (tool_key, glyph, i18n_key, fallback)
    _ANNOTATION_TOOLS = [
        ("select",   "⬚", "annotation_tool_select",   "Select"),
        ("crop",     "✂", "annotation_tool_crop",      "Crop"),
        ("rect",     "▢", "annotation_tool_rect",      "Rectangle"),
        ("ellipse",  "◯", "annotation_tool_ellipse",   "Ellipse"),
        ("line",     "╱", "annotation_tool_line",       "Line"),
        ("arrow",    "→", "annotation_tool_arrow",      "Arrow"),
        ("freehand", "✎", "annotation_tool_freehand",   "Freehand"),
        ("text",     "T", "annotation_tool_text",       "Text"),
        ("mosaic",   "▦", "annotation_tool_mosaic",     "Mosaic"),
        ("blur",     "◌", "annotation_tool_blur",       "Blur"),
    ]

    # Crop aspect ratio presets: (label_key, fallback, ratio_w, ratio_h)
    # ratio 0,0 = free
    _CROP_RATIOS = [
        ("crop_ratio_free",  "Free",     0, 0),
        ("crop_ratio_1_1",   "1 : 1",    1, 1),
        ("crop_ratio_4_3",   "4 : 3",    4, 3),
        ("crop_ratio_3_2",   "3 : 2",    3, 2),
        ("crop_ratio_16_9",  "16 : 9",  16, 9),
        ("crop_ratio_9_16",  "9 : 16",   9, 16),
    ]

    # Size of each tool button in the vertical strip.
    _TOOL_BTN_SIZE = QSize(86, 66)

    def __init__(self, main_gui: GPUImageView):
        super().__init__()
        self._main_gui = main_gui
        self._path: str | None = None
        self._current = Recipe()
        self._committed = Recipe()
        self._suppress_signals = False

        self._undo_stack = QUndoStack(self)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self._DEBOUNCE_MS)
        self._debounce.timeout.connect(self._preview_debounced)

        self._interactive_widgets: list[QWidget] = []

        # Inline annotation canvas — created lazily when an image is bound.
        self._canvas: AnnotationCanvas | None = None
        self._canvas_undo_stack = QUndoStack(self)
        self._canvas_source_path: str | None = None

        # Drawing state (mirrored by the right-panel controls)
        self._draw_color: tuple[int, int, int, int] = (255, 0, 0, 255)

    # ------------------------------------------------------------------
    # Panel builders — called by ImervueMainWindow
    # ------------------------------------------------------------------

    def build_left_panel(self, parent_splitter: QSplitter) -> None:
        """Build a narrow vertical tool strip (annotation + orientation) with a scroll bar."""
        lang = language_wrapper.language_word_dict

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # --- Annotation tools (vertical single-column) ---
        self._tool_buttons: dict[str, QToolButton] = {}
        for tool_key, glyph, i18n_key, fallback in self._ANNOTATION_TOOLS:
            btn = QToolButton()
            label = lang.get(i18n_key, fallback)
            btn.setText(f"{glyph}\n{label}")
            btn.setToolTip(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFixedSize(self._TOOL_BTN_SIZE)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, t=tool_key: self._set_tool(t))
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._interactive_widgets.append(btn)
            self._tool_buttons[tool_key] = btn

        # Default: select tool checked
        if "select" in self._tool_buttons:
            self._tool_buttons["select"].setChecked(True)

        # Crop controls are built in build_right_panel() where there is
        # enough width for the combo box and buttons.

        # --- Separator ---
        layout.addSpacing(4)

        # --- Orientation (also vertical) ---
        orient_buttons: list[tuple[str, str, str, Callable]] = [
            ("⟲", "develop_rotate_ccw", "Rotate 90° CCW", lambda: self._rotate(-1)),
            ("⟳", "develop_rotate_cw",  "Rotate 90° CW",  lambda: self._rotate(1)),
            ("⇆", "develop_flip_h",     "Flip Horizontal", self._flip_h),
            ("⇅", "develop_flip_v",     "Flip Vertical",   self._flip_v),
        ]
        for glyph, i18n_key, fallback, handler in orient_buttons:
            btn = QToolButton()
            label = lang.get(i18n_key, fallback)
            btn.setText(f"{glyph}\n{label}")
            btn.setToolTip(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFixedSize(self._TOOL_BTN_SIZE)
            btn.clicked.connect(handler)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._interactive_widgets.append(btn)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        scroll.setFixedWidth(self._TOOL_BTN_SIZE.width() + 24)
        parent_splitter.addWidget(scroll)

    def build_right_panel(self, parent_splitter: QSplitter) -> None:
        """Build the right panel (drawing props + develop sliders) into *parent_splitter*."""
        lang = language_wrapper.language_word_dict

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ============================================================
        # Crop controls (hidden until crop tool selected)
        # ============================================================
        self._crop_widget = QWidget()
        crop_layout = QVBoxLayout(self._crop_widget)
        crop_layout.setContentsMargins(0, 0, 0, 0)
        crop_layout.setSpacing(4)

        crop_title = QLabel(lang.get("annotation_tool_crop", "Crop"))
        crop_title_font = QFont(crop_title.font())
        crop_title_font.setBold(True)
        crop_title.setFont(crop_title_font)
        crop_layout.addWidget(crop_title)

        self._crop_ratio_combo = QComboBox()
        for label_key, fallback, rw, rh in self._CROP_RATIOS:
            self._crop_ratio_combo.addItem(
                lang.get(label_key, fallback), (rw, rh))
        self._crop_ratio_combo.currentIndexChanged.connect(self._on_crop_ratio_changed)
        crop_layout.addWidget(self._crop_ratio_combo)

        crop_btn_row = QHBoxLayout()
        self._crop_apply_btn = QPushButton(lang.get("crop_apply", "Apply"))
        self._crop_apply_btn.clicked.connect(self._apply_crop)
        self._crop_cancel_btn = QPushButton(lang.get("crop_cancel", "Cancel"))
        self._crop_cancel_btn.clicked.connect(self._cancel_crop)
        crop_btn_row.addWidget(self._crop_apply_btn)
        crop_btn_row.addWidget(self._crop_cancel_btn)
        crop_layout.addLayout(crop_btn_row)

        layout.addWidget(self._crop_widget)
        self._crop_widget.hide()

        # ============================================================
        # Drawing properties
        # ============================================================

        # --- Color ---
        self._color_btn = QToolButton()
        self._color_btn.setText(lang.get("annotation_color", "Color"))
        self._color_btn.setFixedHeight(36)
        from PySide6.QtWidgets import QSizePolicy
        self._color_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_button_style()
        layout.addWidget(self._color_btn)
        self._interactive_widgets.append(self._color_btn)

        # --- Stroke width ---
        sw_label = QLabel(lang.get("annotation_stroke_width_label", "Stroke Width"))
        layout.addWidget(sw_label)

        sw_row = QHBoxLayout()
        sw_row.setContentsMargins(0, 0, 0, 0)
        sw_row.setSpacing(4)
        self._width_slider = QSlider(Qt.Orientation.Horizontal)
        self._width_slider.setRange(1, 40)
        self._width_slider.setValue(3)
        sw_row.addWidget(self._width_slider, 1)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 40)
        self._width_spin.setValue(3)
        self._width_spin.setFixedWidth(60)
        sw_row.addWidget(self._width_spin)
        layout.addLayout(sw_row)
        self._interactive_widgets.extend([self._width_slider, self._width_spin])

        self._width_slider.valueChanged.connect(self._on_stroke_slider)
        self._width_spin.valueChanged.connect(self._on_stroke_spin)

        # --- Brush type ---
        brush_label = QLabel(lang.get("annotation_brush_section", "Brush"))
        layout.addWidget(brush_label)
        brush_grid = QGridLayout()
        brush_grid.setContentsMargins(0, 0, 0, 0)
        brush_grid.setSpacing(3)
        self._brush_buttons: dict[str, QToolButton] = {}
        self._brush_group = QButtonGroup(self)
        self._brush_group.setExclusive(True)
        brush_defs = [
            ("pen",         "✒",  lang.get("annotation_brush_pen",         "Pen")),
            ("marker",      "🖊", lang.get("annotation_brush_marker",      "Marker")),
            ("pencil",      "✏",  lang.get("annotation_brush_pencil",      "Pencil")),
            ("highlighter", "🖍", lang.get("annotation_brush_highlighter", "Highlighter")),
            ("spray",       "💨", lang.get("annotation_brush_spray",       "Spray")),
            ("calligraphy", "🖋", lang.get("annotation_brush_calligraphy", "Calligraphy")),
            ("watercolor",  "🎨", lang.get("annotation_brush_watercolor",  "Watercolor")),
            ("charcoal",    "▪",  lang.get("annotation_brush_charcoal",    "Charcoal")),
            ("crayon",      "🖍", lang.get("annotation_brush_crayon",      "Crayon")),
        ]
        for idx, (key, glyph, label) in enumerate(brush_defs):
            btn = QToolButton()
            btn.setText(f"{glyph} {label}")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _=False, k=key: self._on_brush_selected(k))
            row, col = divmod(idx, 2)
            brush_grid.addWidget(btn, row, col)
            self._brush_buttons[key] = btn
            self._brush_group.addButton(btn)
            self._interactive_widgets.append(btn)
        self._brush_buttons["pen"].setChecked(True)
        layout.addLayout(brush_grid)

        # --- Opacity ---
        op_label = QLabel(lang.get("annotation_opacity", "Opacity"))
        layout.addWidget(op_label)
        op_row = QHBoxLayout()
        op_row.setContentsMargins(0, 0, 0, 0)
        op_row.setSpacing(4)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        op_row.addWidget(self._opacity_slider, 1)
        self._opacity_spin = QSpinBox()
        self._opacity_spin.setRange(0, 100)
        self._opacity_spin.setValue(100)
        self._opacity_spin.setSuffix(" %")
        self._opacity_spin.setFixedWidth(60)
        op_row.addWidget(self._opacity_spin)
        layout.addLayout(op_row)
        self._interactive_widgets.extend([self._opacity_slider, self._opacity_spin])

        self._opacity_slider.valueChanged.connect(self._on_opacity_slider)
        self._opacity_spin.valueChanged.connect(self._on_opacity_spin)

        # --- Font (text tool) ---
        font_label = QLabel(lang.get("annotation_font_section", "Font"))
        layout.addWidget(font_label)

        self._font_combo = QFontComboBox()
        self._font_combo.currentFontChanged.connect(self._on_font_changed)
        layout.addWidget(self._font_combo)
        self._interactive_widgets.append(self._font_combo)

        fs_row = QHBoxLayout()
        fs_row.setContentsMargins(0, 0, 0, 0)
        fs_row.setSpacing(4)
        fs_lbl = QLabel(lang.get("annotation_font_size", "Size"))
        fs_row.addWidget(fs_lbl)
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 200)
        self._font_size_spin.setValue(24)
        self._font_size_spin.setSuffix(" px")
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        fs_row.addWidget(self._font_size_spin, 1)
        layout.addLayout(fs_row)
        self._interactive_widgets.append(self._font_size_spin)

        # --- Annotation Save ---
        ann_btn_row = QHBoxLayout()
        self._btn_ann_save = QPushButton(lang.get("annotation_save", "Save"))
        self._btn_ann_save.clicked.connect(self._save_annotation)
        ann_btn_row.addWidget(self._btn_ann_save)
        self._interactive_widgets.append(self._btn_ann_save)

        self._btn_ann_undo = QPushButton(lang.get("annotation_undo", "Undo"))
        self._btn_ann_undo.clicked.connect(self._canvas_undo_stack.undo)
        ann_btn_row.addWidget(self._btn_ann_undo)
        self._interactive_widgets.append(self._btn_ann_undo)

        self._btn_ann_redo = QPushButton(lang.get("annotation_redo", "Redo"))
        self._btn_ann_redo.clicked.connect(self._canvas_undo_stack.redo)
        ann_btn_row.addWidget(self._btn_ann_redo)
        self._interactive_widgets.append(self._btn_ann_redo)

        layout.addLayout(ann_btn_row)

        # ============================================================
        # Develop sliders (recipe)
        # ============================================================
        layout.addSpacing(8)
        dev_label = QLabel(lang.get("modify_menu_develop", "Develop"))
        dev_font = QFont(dev_label.font())
        dev_font.setBold(True)
        dev_label.setFont(dev_font)
        layout.addWidget(dev_label)

        self._exposure, exp_label = self._make_slider(
            lang.get("develop_exposure", "Exposure"),
            self._EXPOSURE_RANGE,
            self._on_exposure,
        )
        layout.addLayout(self._label_over_slider(exp_label, self._exposure))
        self._exposure_label = exp_label

        self._brightness, br_label = self._make_slider(
            lang.get("develop_brightness", "Brightness"),
            self._COLOR_RANGE,
            self._on_brightness,
        )
        layout.addLayout(self._label_over_slider(br_label, self._brightness))
        self._brightness_label = br_label

        self._contrast, ct_label = self._make_slider(
            lang.get("develop_contrast", "Contrast"),
            self._COLOR_RANGE,
            self._on_contrast,
        )
        layout.addLayout(self._label_over_slider(ct_label, self._contrast))
        self._contrast_label = ct_label

        self._saturation, sat_label = self._make_slider(
            lang.get("develop_saturation", "Saturation"),
            self._COLOR_RANGE,
            self._on_saturation,
        )
        layout.addLayout(self._label_over_slider(sat_label, self._saturation))
        self._saturation_label = sat_label

        # --- Advanced sliders (white balance, tonal regions, vibrance) ---
        self._adv_sliders: dict[str, QSlider] = {}
        self._adv_labels: dict[str, QLabel] = {}
        for field_name, i18n_key, fallback in self._ADVANCED_SLIDERS:
            title = lang.get(i18n_key, fallback)
            slider, label = self._make_slider(
                title,
                self._COLOR_RANGE,
                self._make_advanced_handler(field_name),
            )
            layout.addLayout(self._label_over_slider(label, slider))
            self._adv_sliders[field_name] = slider
            self._adv_labels[field_name] = label

        # --- Recipe Reset / Undo / Redo ---
        btn_row = QHBoxLayout()
        self._btn_reset = QPushButton(lang.get("develop_reset", "Reset"))
        self._btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(self._btn_reset)
        self._interactive_widgets.append(self._btn_reset)

        self._btn_undo = QPushButton(lang.get("develop_undo", "Undo"))
        self._btn_undo.clicked.connect(self._undo_stack.undo)
        btn_row.addWidget(self._btn_undo)
        self._interactive_widgets.append(self._btn_undo)

        self._btn_redo = QPushButton(lang.get("develop_redo", "Redo"))
        self._btn_redo.clicked.connect(self._undo_stack.redo)
        btn_row.addWidget(self._btn_redo)
        self._interactive_widgets.append(self._btn_redo)

        layout.addLayout(btn_row)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setMinimumWidth(260)
        parent_splitter.addWidget(scroll)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_slider(
        self,
        title: str,
        limit: int,
        on_change: Callable[[int], None],
    ) -> tuple[QSlider, QLabel]:
        label = QLabel(f"{title}: 0")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-limit, limit)
        slider.setValue(0)
        slider.valueChanged.connect(on_change)
        slider.setProperty("_title", title)
        self._interactive_widgets.append(slider)
        return slider, label

    @staticmethod
    def _label_over_slider(label: QLabel, slider: QSlider) -> QVBoxLayout:
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(label)
        v.addWidget(slider)
        return v

    # ------------------------------------------------------------------
    # Public API — called by GPUImageView / ImervueMainWindow
    # ------------------------------------------------------------------

    def canvas(self) -> AnnotationCanvas | None:
        """Return the current inline AnnotationCanvas, or None."""
        return self._canvas

    def bind_to_path(self, path: str | None) -> None:
        """Load the recipe for ``path`` (or clear if None) and refresh the UI.

        Also creates / updates the inline AnnotationCanvas with the
        image at *path*.  When re-binding to the *same* path (e.g. after a
        tab switch) the working recipe (``_current``) is preserved so unsaved
        slider/rotate/flip changes are not lost.
        """
        self._path = path
        if path is None:
            self._current = Recipe()
            self._committed = Recipe()
            self._set_enabled(False)
            self._sync_sliders()
            self._destroy_canvas()
            return

        if self._canvas_source_path != path:
            # New image — load the saved recipe from the store.
            self._current = recipe_store.get_for_path(path) or Recipe()
            self._committed = Recipe.from_dict(self._current.to_dict())
            self._set_enabled(True)
            self._sync_sliders()
            self._create_canvas(path)
        else:
            # Same path — keep the working recipe to preserve unsaved edits.
            self._set_enabled(True)

    def current_recipe(self) -> Recipe:
        return Recipe.from_dict(self._current.to_dict())

    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    # ------------------------------------------------------------------
    # Inline AnnotationCanvas management
    # ------------------------------------------------------------------

    def _load_image_with_recipe(self, path: str) -> Image.Image | None:
        """Load *path* from disk and apply the current recipe.

        Returns an RGBA PIL image or None on failure.
        """
        try:
            img = Image.open(path)
            if img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGBA")
            else:
                img.load()
        except Exception:
            logger.exception("Failed to load image: %s", path)
            return None

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if not self._current.is_identity():
            arr = self._current.apply(np.array(img))
            img = Image.fromarray(arr, "RGBA")
        return img

    def _create_canvas(self, path: str) -> None:
        """Load *path* as PIL and create a fresh AnnotationCanvas."""
        from Imervue.gui.annotation_dialog import AnnotationCanvas

        img = self._load_image_with_recipe(path)
        if img is None:
            self._destroy_canvas()
            return

        # Tear down old canvas completely before creating a new one
        self._cleanup_old_canvas()

        self._canvas = AnnotationCanvas(img, self._canvas_undo_stack)
        self._canvas_source_path = path

        # Apply current drawing state to the new canvas
        self._canvas.set_color(self._draw_color)
        self._canvas.set_stroke_width(self._width_slider.value())
        self._canvas.set_brush_opacity(self._opacity_slider.value())

        # Allow Left/Right arrow keys to switch images
        self._canvas.navigate_image.connect(self._on_navigate_image)

        # Insert the canvas into the modify splitter (index 1).
        splitter = getattr(self._main_gui.main_window, "_modify_splitter", None)
        if splitter is not None:
            splitter.insertWidget(1, self._canvas)
            splitter.setStretchFactor(1, 1)

    def _cleanup_old_canvas(self) -> None:
        """Disconnect signals, clear undo stack, and detach the old canvas.

        Avoids both ``shiboken_delete`` and ``deleteLater`` — both of them
        race with Qt's widget-tree teardown on Windows and cause heap
        corruption (0xC0000374).  Instead we:

        1. Clear shiboken-managed Python attrs on the canvas so their C++
           counterparts are freed NOW (while Qt is still alive), rather than
           during Python-shutdown GC when Qt is half-destroyed.
        2. Detach from the splitter (``setParent(None)``).
        3. Drop the Python reference — CPython's refcount immediately frees
           the wrapper; shiboken sees no parent → deletes the C++ QWidget
           deterministically, all within normal execution.
        """
        self._canvas_undo_stack.clear()
        if self._canvas is not None:
            # Disconnect signals we connected
            with contextlib.suppress(RuntimeError, TypeError):
                self._canvas.navigate_image.disconnect(self._on_navigate_image)
            # Cancel any in-flight text editor (its deleteLater would
            # otherwise outlive the canvas).
            with contextlib.suppress(Exception):
                self._canvas._cancel_text_edit()
            # Release shiboken-tracked objects held by the canvas so they
            # are freed deterministically right now.
            with contextlib.suppress(Exception):
                self._canvas._base_qimg = None
                self._canvas._preview_qimg = None
            self._canvas.hide()
            self._canvas.setParent(None)
            self._canvas = None

    def _destroy_canvas(self) -> None:
        self._debounce.stop()
        self._cleanup_old_canvas()
        self._canvas_source_path = None

    def _refresh_canvas_base(self) -> None:
        """Re-apply the current recipe to the raw image and update the canvas.

        Called when recipe sliders change without a path change.  If the
        image geometry (dimensions) changed — e.g. after a rotation — any
        existing annotations are cleared because their coordinates would be
        invalid in the new coordinate space.
        """
        if self._canvas is None or self._canvas_source_path is None:
            return
        img = self._load_image_with_recipe(self._canvas_source_path)
        if img is None:
            return

        old_w, old_h = self._canvas._base.width, self._canvas._base.height
        if (img.width, img.height) != (old_w, old_h):
            self._canvas.set_annotations([])
            self._canvas.clear_crop()

        self._canvas._set_base_image(img)

    # ------------------------------------------------------------------
    # Left-panel tool selection
    # ------------------------------------------------------------------

    def _set_tool(self, tool: str) -> None:
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

    def _apply_crop(self) -> None:
        if self._canvas is None or self._canvas_source_path is None:
            return
        crop_rect = self._canvas.get_crop_rect()
        if crop_rect is None:
            return
        x, y, w, h = crop_rect
        if w < 2 or h < 2:
            return
        base = self._canvas.get_base_pil()
        cropped = base.crop((x, y, x + w, y + h))
        # Save atomically
        path = self._canvas_source_path
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        ext = target.suffix.lower()
        fmt_map = {
            ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
            ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = fmt_map.get(ext, "PNG")
        try:
            save_img = cropped
            if fmt == "JPEG" and save_img.mode == "RGBA":
                save_img = save_img.convert("RGB")
            save_img.save(str(tmp), format=fmt)
            os.replace(tmp, target)
        except Exception:
            logger.exception("Failed to save crop to %s", path)
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return
        # The recipe adjustments are now baked into the saved file — reset
        # the recipe so they won't be applied again by the viewer.
        self._current = Recipe()
        self._committed = Recipe()
        recipe_store.set_for_path(path, Recipe())
        self._sync_sliders()

        # Reload
        self._canvas.clear_crop()
        self._create_canvas(path)
        try:
            from Imervue.gpu_image_view.images.image_loader import open_path
            self._main_gui._clear_deep_zoom()
            open_path(main_gui=self._main_gui, path=path)
        except Exception:
            logger.exception("Viewer reload after crop failed")

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

    def _on_stroke_slider(self, v: int) -> None:
        self._width_spin.blockSignals(True)
        self._width_spin.setValue(v)
        self._width_spin.blockSignals(False)
        if self._canvas is not None:
            self._canvas.set_stroke_width(v)

    def _on_stroke_spin(self, v: int) -> None:
        self._width_slider.blockSignals(True)
        self._width_slider.setValue(v)
        self._width_slider.blockSignals(False)
        if self._canvas is not None:
            self._canvas.set_stroke_width(v)

    def _on_brush_selected(self, key: str) -> None:
        if self._canvas is not None:
            self._canvas.set_brush_type(key)

    def _on_opacity_slider(self, v: int) -> None:
        self._opacity_spin.blockSignals(True)
        self._opacity_spin.setValue(v)
        self._opacity_spin.blockSignals(False)
        if self._canvas is not None:
            self._canvas.set_brush_opacity(v)

    def _on_opacity_spin(self, v: int) -> None:
        self._opacity_slider.blockSignals(True)
        self._opacity_slider.setValue(v)
        self._opacity_slider.blockSignals(False)
        if self._canvas is not None:
            self._canvas.set_brush_opacity(v)

    def _on_font_changed(self, font: QFont) -> None:
        if self._canvas is not None:
            self._canvas.set_font_family(font.family())

    def _on_font_size_changed(self, v: int) -> None:
        if self._canvas is not None:
            self._canvas.set_font_size(v)

    # ------------------------------------------------------------------
    # Image navigation (Left / Right arrow in canvas)
    # ------------------------------------------------------------------

    def _on_navigate_image(self, direction: int) -> None:
        """Switch to prev/next image via the viewer, then rebind the canvas."""
        from Imervue.gpu_image_view.actions.select import (
            switch_to_next_image,
            switch_to_previous_image,
        )
        viewer = self._main_gui
        if direction > 0:
            switch_to_next_image(main_gui=viewer)
        else:
            switch_to_previous_image(main_gui=viewer)
        # Rebind to the new current image
        images = viewer.model.images
        path = None
        if images and 0 <= viewer.current_index < len(images):
            path = images[viewer.current_index]
        self.bind_to_path(path)

    # ------------------------------------------------------------------
    # Save annotation
    # ------------------------------------------------------------------

    def _save_annotation(self) -> None:
        """Bake annotations into the image and save back to the source file."""
        if self._canvas is None or self._canvas_source_path is None:
            return
        from Imervue.gui.annotation_models import bake

        path = self._canvas_source_path
        img = bake(self._canvas.get_base_pil(), self._canvas.get_annotations())
        ext = Path(path).suffix.lower()
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        fmt_map = {
            ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
            ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = fmt_map.get(ext, "PNG")
        try:
            save_img = img
            if fmt == "JPEG" and save_img.mode == "RGBA":
                save_img = save_img.convert("RGB")
            save_img.save(str(tmp), format=fmt)
            os.replace(tmp, target)
        except Exception:
            logger.exception("Failed to save annotation to %s", path)
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return

        # The recipe adjustments are now baked into the saved file — reset
        # the recipe so they won't be applied again by the viewer.
        self._current = Recipe()
        self._committed = Recipe()
        recipe_store.set_for_path(path, Recipe())
        self._sync_sliders()

        # Reload the image in both the canvas and the main viewer
        self._create_canvas(path)
        try:
            from Imervue.gpu_image_view.images.image_loader import open_path
            self._main_gui._clear_deep_zoom()
            open_path(main_gui=self._main_gui, path=path)
        except Exception:
            logger.exception("Viewer reload after annotation save failed")

    # ------------------------------------------------------------------
    # Slider → recipe mapping
    # ------------------------------------------------------------------

    def _set_enabled(self, enabled: bool) -> None:
        for w in self._interactive_widgets:
            w.setEnabled(enabled)

    def _sync_sliders(self) -> None:
        """Push recipe values into the sliders without triggering emissions."""
        self._suppress_signals = True
        try:
            self._exposure.setValue(int(round(self._current.exposure * 100)))
            self._brightness.setValue(int(round(self._current.brightness * 100)))
            self._contrast.setValue(int(round(self._current.contrast * 100)))
            self._saturation.setValue(int(round(self._current.saturation * 100)))
            for field_name, slider in self._adv_sliders.items():
                value = getattr(self._current, field_name)
                slider.setValue(int(round(value * 100)))
        finally:
            self._suppress_signals = False
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        lang = language_wrapper.language_word_dict
        self._exposure_label.setText(
            f"{lang.get('develop_exposure', 'Exposure')}: {self._current.exposure:+.2f}"
        )
        bri = int(self._current.brightness * 100)
        con = int(self._current.contrast * 100)
        sat = int(self._current.saturation * 100)
        self._brightness_label.setText(
            f"{lang.get('develop_brightness', 'Brightness')}: {bri:+d}"
        )
        self._contrast_label.setText(
            f"{lang.get('develop_contrast', 'Contrast')}: {con:+d}"
        )
        self._saturation_label.setText(
            f"{lang.get('develop_saturation', 'Saturation')}: {sat:+d}"
        )
        for field_name, i18n_key, fallback in self._ADVANCED_SLIDERS:
            value_pct = int(round(getattr(self._current, field_name) * 100))
            title = lang.get(i18n_key, fallback)
            self._adv_labels[field_name].setText(f"{title}: {value_pct:+d}")

    def _make_advanced_handler(self, field_name: str) -> Callable[[int], None]:
        """Return a slider handler that writes to ``self._current.<field_name>``."""
        def handler(v: int) -> None:
            if self._suppress_signals:
                return
            setattr(self._current, field_name, v / 100.0)
            self._refresh_labels()
            self._schedule_preview()
        return handler

    def _on_exposure(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.exposure = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_brightness(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.brightness = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_contrast(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.contrast = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_saturation(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.saturation = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    # ------------------------------------------------------------------
    # Rotate / flip — preview only (no commit until save)
    # ------------------------------------------------------------------

    def _rotate(self, delta: int) -> None:
        if self._path is None:
            return
        self._current.rotate_steps = (self._current.rotate_steps + delta) % 4
        self._refresh_canvas_base()

    def _flip_h(self) -> None:
        if self._path is None:
            return
        self._current.flip_h = not self._current.flip_h
        self._refresh_canvas_base()

    def _flip_v(self) -> None:
        if self._path is None:
            return
        self._current.flip_v = not self._current.flip_v
        self._refresh_canvas_base()

    def _reset(self) -> None:
        if self._path is None:
            return
        self._current = Recipe()
        self._sync_sliders()
        self._refresh_canvas_base()

    # ------------------------------------------------------------------
    # Preview logic — debounced canvas refresh, no commit to recipe_store
    # ------------------------------------------------------------------

    def _schedule_preview(self) -> None:
        """Debounce canvas refresh so rapid slider drags don't reload on
        every tick."""
        self._debounce.start()

    def _preview_debounced(self) -> None:
        self._refresh_canvas_base()
