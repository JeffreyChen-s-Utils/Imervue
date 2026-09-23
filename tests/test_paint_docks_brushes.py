"""Characterisation tests for ``BrushDock``'s form layout and control wiring.

Pins the form rows (order, labels, widgets), slider ranges, tooltips and the
field each control writes back to the tool state, so restructuring the
constructor cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QPushButton, QSlider, QSpinBox

from Imervue.paint import tool_state as ts
from Imervue.paint.docks import brushes
from Imervue.paint.docks.brushes import BrushDock
from Imervue.user_settings.user_setting_dict import user_setting_dict

# (attribute, form label, brush field)
_PERCENT_SLIDERS = [
    ("_opacity", "Opacity:", "opacity"),
    ("_hardness", "Hardness:", "hardness"),
    ("_density", "Density:", "density"),
    ("_stabilizer", "Stabilizer:", "stabilizer"),
    ("_scatter", "Scatter:", "scatter"),
    ("_color_jitter", "Colour jitter:", "color_jitter"),
]


@pytest.fixture(autouse=True)
def _english_and_clean_state(monkeypatch):
    monkeypatch.setattr(brushes.language_wrapper, "language_word_dict", {})
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    return ts.load_tool_state()


@pytest.fixture
def dock(qapp, state):
    widget = BrushDock(state)
    yield widget
    widget.deleteLater()


def _rows(dock):
    form = dock.widget().layout()
    assert isinstance(form, QFormLayout)
    rows = []
    for row in range(form.rowCount()):
        label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
        label_text = label.widget().text() if label is not None else None
        rows.append((label_text, field.widget()))
    return rows


def test_form_rows_in_order(dock):
    rows = _rows(dock)
    assert rows == [
        ("Kind:", dock._kind), ("Size:", dock._size),  # noqa: SLF001
        ("Opacity:", dock._opacity), ("Hardness:", dock._hardness),  # noqa: SLF001
        ("Density:", dock._density), ("Stabilizer:", dock._stabilizer),  # noqa: SLF001
        ("Scatter:", dock._scatter), ("Colour jitter:", dock._color_jitter),  # noqa: SLF001
        (None, dock._follow_tilt), ("Blend:", dock._blend),  # noqa: SLF001
        (None, dock._presets_btn),  # noqa: SLF001
    ]
    assert dock.windowTitle() == "Brush"


def test_widget_types_and_ranges(dock):
    assert isinstance(dock._kind, QComboBox)  # noqa: SLF001
    assert isinstance(dock._size, QSpinBox)  # noqa: SLF001
    assert (dock._size.minimum(), dock._size.maximum()) == (  # noqa: SLF001
        ts.BRUSH_SIZE_MIN, ts.BRUSH_SIZE_MAX)
    for attr, *_rest in _PERCENT_SLIDERS:
        slider = getattr(dock, attr)
        assert isinstance(slider, QSlider), attr
        assert (slider.minimum(), slider.maximum()) == (0, 100), attr
    assert isinstance(dock._follow_tilt, QCheckBox)  # noqa: SLF001
    assert dock._follow_tilt.text() == "Follow pen tilt"  # noqa: SLF001
    assert isinstance(dock._presets_btn, QPushButton)  # noqa: SLF001
    assert dock._presets_btn.text() == "Presets…"  # noqa: SLF001


def test_combo_contents(dock):
    kinds = [dock._kind.itemData(i) for i in range(dock._kind.count())]  # noqa: SLF001
    assert kinds == list(ts.BRUSH_KINDS)
    blends = [dock._blend.itemData(i) for i in range(dock._blend.count())]  # noqa: SLF001
    assert blends == list(ts.BLEND_MODES)
    assert dock._kind.itemText(0) == ts.BRUSH_KINDS[0].capitalize()  # noqa: SLF001


def test_tooltips(dock):
    expected = {
        "_kind": "Brush family — pen / pencil / marker / airbrush / watercolor",
        "_size": "Brush diameter in canvas pixels — [ smaller, ] larger",
        "_opacity": "Per-dab paint coverage (0–100%)",
        "_hardness": "Edge falloff — 0% soft, 100% hard disc",
        "_density": "Per-dab opacity multiplier — lower deposits less ink per stamp",
        "_stabilizer": "Smooth jittery input — 0 off, 100 maximum lag for a clean line",
        "_scatter": "Random per-dab offset, as a fraction of brush size",
        "_color_jitter": "Random hue / luma drift along the stroke",
        "_follow_tilt": "Stretch the brush kernel along the tablet pen tilt direction",
        "_blend": "Compositing mode applied at every dab — Normal is alpha-over",
    }
    for attr, tip in expected.items():
        assert getattr(dock, attr).toolTip() == tip, attr


def test_controls_start_from_state(dock, state):
    brush = state.brush
    assert dock._kind.currentData() == brush.kind  # noqa: SLF001
    assert dock._size.value() == brush.size  # noqa: SLF001
    for attr, _label, field in _PERCENT_SLIDERS:
        assert getattr(dock, attr).value() == round(getattr(brush, field) * 100), attr
    assert dock._follow_tilt.isChecked() == bool(brush.follow_tilt)  # noqa: SLF001
    assert dock._blend.currentData() == brush.blend_mode  # noqa: SLF001


@pytest.mark.parametrize(("attr", "field"), [(a, f) for a, _l, f in _PERCENT_SLIDERS])
def test_percent_slider_writes_fraction_back(dock, state, attr, field):
    slider = getattr(dock, attr)
    target = 37 if slider.value() != 37 else 38
    slider.setValue(target)
    assert getattr(state.brush, field) == pytest.approx(target / 100.0)


def test_follow_tilt_writes_back(dock, state):
    before = bool(state.brush.follow_tilt)
    dock._follow_tilt.setChecked(not before)  # noqa: SLF001
    assert bool(state.brush.follow_tilt) is (not before)


def test_presets_button_opens_dialog_for_state(dock, state, monkeypatch):
    from Imervue.paint import brush_preset_dialog
    opened = []
    monkeypatch.setattr(brush_preset_dialog, "open_brush_preset_dialog",
                        lambda st, parent=None: opened.append((st, parent)))
    dock._presets_btn.click()  # noqa: SLF001
    assert opened == [(state, dock)]


def test_destroying_dock_unsubscribes(qapp, state, monkeypatch):
    dropped = []
    real_subscribe = state.subscribe

    def spy(callback):
        unsubscribe = real_subscribe(callback)
        return lambda: (dropped.append(True), unsubscribe())

    monkeypatch.setattr(state, "subscribe", spy)
    widget = BrushDock(state)
    widget.destroyed.emit()
    assert dropped == [True]
    widget.deleteLater()
