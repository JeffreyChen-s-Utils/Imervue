"""Tests for the linked slider + spin box helper."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QSlider, QSpinBox, QWidget

from Imervue.gui.slider_spin import link_slider_spin, make_slider_spin


@pytest.fixture
def parent(qapp):
    widget = QWidget(None)
    yield widget
    widget.deleteLater()


def test_make_builds_matching_ranges_and_value(parent):
    slider, spin, row = make_slider_spin(parent, 1, 40, 3)
    assert (slider.minimum(), slider.maximum(), slider.value()) == (1, 40, 3)
    assert (spin.minimum(), spin.maximum(), spin.value()) == (1, 40, 3)
    assert row.count() == 2


def test_suffix_is_applied_only_when_given(parent):
    _s, with_suffix, _r = make_slider_spin(parent, 0, 100, 50, suffix=" %")
    _s2, plain, _r2 = make_slider_spin(parent, 0, 100, 50)
    assert with_suffix.suffix() == " %"
    assert plain.suffix() == ""


def test_moving_the_slider_updates_the_spin_and_reports_once(parent):
    seen: list[int] = []
    slider, spin, _row = make_slider_spin(parent, 0, 100, 10, on_change=seen.append)
    slider.setValue(42)
    assert spin.value() == 42
    assert seen == [42]


def test_editing_the_spin_updates_the_slider_and_reports_once(parent):
    seen: list[int] = []
    slider, spin, _row = make_slider_spin(parent, 0, 100, 10, on_change=seen.append)
    spin.setValue(7)
    assert slider.value() == 7
    assert seen == [7]


def test_works_without_a_callback(parent):
    slider, spin, _row = make_slider_spin(parent, 0, 10, 0)
    slider.setValue(10)
    assert spin.value() == 10


def test_values_outside_the_range_are_clamped_on_both(parent):
    slider, spin, _row = make_slider_spin(parent, 1, 40, 3)
    spin.setValue(99)
    assert (spin.value(), slider.value()) == (40, 40)


def test_link_existing_widgets(parent):
    slider = QSlider(parent)
    spin = QSpinBox(parent)
    slider.setRange(0, 5)
    spin.setRange(0, 5)
    seen: list[int] = []
    link_slider_spin(slider, spin, seen.append)
    slider.setValue(5)
    spin.setValue(2)
    assert (slider.value(), spin.value()) == (2, 2)
    assert seen == [5, 2]


def test_default_spin_width_and_spacing(parent):
    _slider, spin, row = make_slider_spin(parent, 0, 10, 0)
    assert spin.maximumWidth() == 70
    assert row.spacing() == 6


def test_custom_spin_width_and_spacing(parent):
    _slider, spin, row = make_slider_spin(parent, 0, 10, 0, spin_width=60, spacing=4)
    assert spin.maximumWidth() == 60
    assert row.spacing() == 4


def test_parent_may_be_none(qapp):
    slider, spin, row = make_slider_spin(None, 0, 10, 5)
    assert slider.parent() is None and spin.parent() is None
    row.deleteLater()
