"""Shared settings widgets for the safety_review dialogs.

``_build_mode_row`` adds the detection-mode, censor-style, censor-area,
confidence, expand and category controls to a layout; ``_SettingsDialogBase``
adds the block-size / padding rows the single and batch dialogs share.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
)

from safety_review._constants import (
    ALL_CATEGORIES,
    CAT_ANUS,
    CAT_GENITALIA,
    CAT_NIPPLE,
    CAT_SEXUAL_ACT,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_CATEGORIES,
    DEFAULT_PADDING,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    SHAPE_ELLIPSE,
    SHAPE_PRECISE,
    SHAPE_RECT,
    STYLE_BLACK,
    STYLE_BLUR,
    STYLE_MOSAIC,
    _MODE_DEFAULTS,
)
from safety_review._dialogs_common import (
    _KEY_BLOCK_SIZE,
    _KEY_PADDING,
    _WorkerHostMixin,
    _selected_categories,
)


def _build_mode_combo(layout, lang):
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel(lang.get("safety_review_mode", "Detection mode:")))
    mode_combo = QComboBox()
    mode_combo.addItem(lang.get("safety_review_mode_auto", "Auto"), MODE_AUTO)
    mode_combo.addItem(lang.get("safety_review_mode_real", "Real Photo"), MODE_REAL)
    mode_combo.addItem(
        lang.get("safety_review_mode_anime", "Anime / Illustration"), MODE_ANIME)
    mode_row.addWidget(mode_combo, 1)
    layout.addLayout(mode_row)
    return mode_combo


def _build_style_combo(layout, lang):
    style_row = QHBoxLayout()
    style_row.addWidget(QLabel(lang.get("safety_review_style", "Censor style:")))
    style_combo = QComboBox()
    style_combo.addItem(
        lang.get("safety_review_style_mosaic", "Mosaic"), STYLE_MOSAIC)
    style_combo.addItem(
        lang.get("safety_review_style_blur", "Gaussian Blur"), STYLE_BLUR)
    style_combo.addItem(
        lang.get("safety_review_style_black", "Black Bar"), STYLE_BLACK)
    style_row.addWidget(style_combo, 1)
    layout.addLayout(style_row)
    return style_combo


def _build_shape_combo(layout, lang):
    shape_row = QHBoxLayout()
    shape_row.addWidget(QLabel(lang.get("safety_review_shape", "Censor area:")))
    shape_combo = QComboBox()
    shape_combo.addItem(
        lang.get("safety_review_shape_ellipse", "Ellipse (tighter)"), SHAPE_ELLIPSE)
    shape_combo.addItem(
        lang.get("safety_review_shape_rect", "Rectangle (whole box)"), SHAPE_RECT)
    shape_combo.addItem(
        lang.get("safety_review_shape_precise", "Precise (pixel-level, slower)"),
        SHAPE_PRECISE)
    shape_row.addWidget(shape_combo, 1)
    layout.addLayout(shape_row)

    hint = QLabel("")
    hint.setWordWrap(True)
    hint.setVisible(False)
    layout.addWidget(hint)

    def _update_hint():
        if shape_combo.currentData() != SHAPE_PRECISE:
            hint.setVisible(False)
            return
        from safety_review._detection import _precise_backend_available
        if _precise_backend_available():
            hint.setText(lang.get(
                "safety_review_precise_ok",
                "Precise: real pixel-level segmentation is available."))
        else:
            hint.setText(lang.get(
                "safety_review_precise_fallback",
                "Precise will fall back to an ellipse — the segmentation model "
                "isn't installed yet (it downloads on the first precise run)."))
        hint.setVisible(True)

    shape_combo.currentIndexChanged.connect(_update_hint)
    _update_hint()
    return shape_combo


def _build_spin_row(layout, label_text, spin):
    row = QHBoxLayout()
    row.addWidget(QLabel(label_text))
    row.addWidget(spin)
    layout.addLayout(row)


def _build_category_checks(layout, lang):
    layout.addWidget(QLabel(
        lang.get("safety_review_categories", "Detection categories:")))
    cat_display = {
        CAT_GENITALIA: lang.get("safety_review_cat_genitalia",
                                "Genitalia (penis / vagina)"),
        CAT_ANUS: lang.get("safety_review_cat_anus", "Anus"),
        CAT_NIPPLE: lang.get("safety_review_cat_nipple", "Nipple / Breast"),
        CAT_SEXUAL_ACT: lang.get("safety_review_cat_sexual_act",
                                 "Sexual Act (anime only)"),
    }
    cat_checks: dict[str, QCheckBox] = {}
    cat_row = QHBoxLayout()
    for cat in ALL_CATEGORIES:
        cb = QCheckBox(cat_display[cat])
        cb.setChecked(cat in DEFAULT_CATEGORIES)
        cat_checks[cat] = cb
        cat_row.addWidget(cb)
    layout.addLayout(cat_row)
    return cat_checks


def _build_mode_row(layout, lang):
    """Add detection-mode combo, style combo, confidence, expand%,
    and category checkboxes to *layout*.

    Returns (mode_combo, conf_spin, expand_spin, style_combo, cat_checks,
    shape_combo). ``cat_checks`` is a dict  {category_name: QCheckBox}.
    """
    mode_combo = _build_mode_combo(layout, lang)
    style_combo = _build_style_combo(layout, lang)
    shape_combo = _build_shape_combo(layout, lang)

    conf_spin = QDoubleSpinBox()
    conf_spin.setRange(0.01, 1.0)
    conf_spin.setSingleStep(0.05)
    conf_spin.setDecimals(2)
    conf_spin.setValue(_MODE_DEFAULTS[MODE_AUTO]["confidence"])
    _build_spin_row(
        layout, lang.get("safety_review_confidence", "Min confidence:"), conf_spin)

    expand_spin = QSpinBox()
    expand_spin.setRange(0, 200)
    expand_spin.setSingleStep(10)
    expand_spin.setValue(_MODE_DEFAULTS[MODE_AUTO]["expand_pct"])
    expand_spin.setSuffix("%")
    _build_spin_row(
        layout,
        lang.get("safety_review_expand_pct", "Expand detection box (%):"),
        expand_spin)

    cat_checks = _build_category_checks(layout, lang)

    def _on_mode_changed(index):
        mode = mode_combo.itemData(index)
        defaults = _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])
        conf_spin.setValue(defaults["confidence"])
        expand_spin.setValue(defaults["expand_pct"])
        sa_cb = cat_checks[CAT_SEXUAL_ACT]
        sa_cb.setEnabled(mode != MODE_REAL)
        if mode == MODE_REAL:
            sa_cb.setChecked(False)

    mode_combo.currentIndexChanged.connect(_on_mode_changed)
    _on_mode_changed(mode_combo.currentIndex())

    return mode_combo, conf_spin, expand_spin, style_combo, cat_checks, shape_combo


class _SettingsDialogBase(_WorkerHostMixin, QDialog):
    """Common block-size / padding rows and overwrite wiring for the
    single + batch dialogs."""

    def _build_block_padding_rows(self, layout):
        self._block_spin = QSpinBox()
        self._block_spin.setRange(2, 64)
        self._block_spin.setValue(DEFAULT_BLOCK_SIZE)
        _build_spin_row(
            layout,
            self._lang.get(_KEY_BLOCK_SIZE, "Mosaic block size (px):"),
            self._block_spin)

        self._padding_spin = QSpinBox()
        self._padding_spin.setRange(0, 200)
        self._padding_spin.setValue(DEFAULT_PADDING)
        _build_spin_row(
            layout,
            self._lang.get(_KEY_PADDING, "Padding around region (px):"),
            self._padding_spin)

    def _on_mode_changed_padding(self, index):
        mode = self._mode_combo.itemData(index)
        self._padding_spin.setValue(
            _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])["padding"])

    def _collect_settings(self):
        return {
            "bs": self._block_spin.value(),
            "pad": self._padding_spin.value(),
            "mode": self._mode_combo.currentData(),
            "conf": self._conf_spin.value(),
            "expand": self._expand_spin.value(),
            "style": self._style_combo.currentData(),
            "categories": _selected_categories(self._cat_checks),
            "shape": self._shape_combo.currentData(),
        }
