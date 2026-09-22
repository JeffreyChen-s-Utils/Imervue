"""The Modify tab's right-hand properties panel.

Crop controls, drawing properties (colour, stroke width, brush, opacity,
font), annotation save / undo / redo, the develop sliders and the recipe
reset / undo / redo row. :class:`DevelopRightPanelMixin` builds it onto the
owning :class:`~Imervue.gui.develop_panel.DevelopPanel`, whose attributes the
widgets are stored on.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFontComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui.modify_splitter import RIGHT_PANEL_WIDTH
from Imervue.gui.slider_spin import make_slider_spin
from Imervue.multi_language.language_wrapper import language_wrapper


# The Modify panel is narrower than the annotation dialog's properties panel.
_SPIN_WIDTH = 60
_ROW_SPACING = 4


class DevelopRightPanelMixin:
    """Builds the right properties panel of :class:`DevelopPanel`."""

    def build_right_panel(self, parent_splitter: QSplitter) -> None:
        """Build the right panel (drawing props + develop sliders) into *parent_splitter*."""
        lang = language_wrapper.language_word_dict

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(self._build_crop_controls(lang))
        self._build_drawing_properties(layout, lang)
        self._build_annotation_buttons(layout, lang)
        self._build_develop_sliders(layout, lang)
        self._build_recipe_buttons(layout, lang)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setMinimumWidth(RIGHT_PANEL_WIDTH)
        parent_splitter.addWidget(scroll)

    def _build_crop_controls(self, lang: dict) -> QWidget:
        """Crop ratio picker and apply / cancel; hidden until the crop tool is picked."""
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
        self._crop_widget.hide()
        return self._crop_widget

    def _build_drawing_properties(self, layout: QVBoxLayout, lang: dict) -> None:
        """Colour, stroke width, brush type, opacity and font controls."""
        # --- Color ---
        self._color_btn = QToolButton()
        self._color_btn.setText(lang.get("annotation_color", "Color"))
        self._color_btn.setFixedHeight(36)
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

        self._width_slider, self._width_spin, sw_row = make_slider_spin(
            None, 1, 40, 3, spin_width=_SPIN_WIDTH, spacing=_ROW_SPACING,
            on_change=self._on_stroke_width)
        layout.addLayout(sw_row)
        self._interactive_widgets.extend([self._width_slider, self._width_spin])

        self._build_brush_buttons(layout, lang)

        # --- Opacity ---
        op_label = QLabel(lang.get("annotation_opacity", "Opacity"))
        layout.addWidget(op_label)
        self._opacity_slider, self._opacity_spin, op_row = make_slider_spin(
            None, 0, 100, 100, suffix=" %", spin_width=_SPIN_WIDTH,
            spacing=_ROW_SPACING, on_change=self._on_opacity)
        layout.addLayout(op_row)
        self._interactive_widgets.extend([self._opacity_slider, self._opacity_spin])

        self._build_font_controls(layout, lang)

    def _build_brush_buttons(self, layout: QVBoxLayout, lang: dict) -> None:
        """Exclusive grid of brush-type buttons; the pen starts checked."""
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

    def _build_font_controls(self, layout: QVBoxLayout, lang: dict) -> None:
        """Font family and size for the text tool."""
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

    def _build_annotation_buttons(self, layout: QVBoxLayout, lang: dict) -> None:
        """Annotation save / undo / redo row."""
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

    def _build_develop_sliders(self, layout: QVBoxLayout, lang: dict) -> None:
        """Exposure / brightness / contrast / saturation plus the advanced sliders."""
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

    def _build_recipe_buttons(self, layout: QVBoxLayout, lang: dict) -> None:
        """Recipe reset / undo / redo row."""
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
        # Tooltip carries the title + range so hover surfaces the
        # adjustment direction even when narrow panels clip the
        # surrounding label.
        slider.setToolTip(
            f"{title} — drag left for −{limit}, right for +{limit}",
        )
        self._interactive_widgets.append(slider)
        return slider, label

    @staticmethod
    def _label_over_slider(label: QLabel, slider: QSlider) -> QVBoxLayout:
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(label)
        v.addWidget(slider)
        return v

    def _on_stroke_width(self, width: int) -> None:
        if self._canvas is not None:
            self._canvas.set_stroke_width(width)

    def _on_opacity(self, opacity: int) -> None:
        if self._canvas is not None:
            self._canvas.set_brush_opacity(opacity)
