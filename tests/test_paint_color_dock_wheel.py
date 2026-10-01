"""The Paint Color dock carries the hue-ring + SV-triangle wheel.

``paint/color_wheel_widget.py`` was built and tested but no dock showed it.
The Color dock now puts it under the swatches: picking on it sets the
foreground, and a foreground set anywhere else moves its marker.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.color_wheel_widget import ColorWheelWidget
from Imervue.paint.dock_panels import ColorDock
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def dock(qapp):
    state = ts.load_tool_state()
    state.set_foreground((200, 40, 40))
    widget = ColorDock(state)
    yield widget
    widget.deleteLater()


def test_the_wheel_starts_on_the_foreground(dock):
    assert isinstance(dock._wheel, ColorWheelWidget)
    assert dock._wheel.color() == (200, 40, 40)


def test_picking_on_the_wheel_sets_the_foreground_and_the_sliders(dock):
    dock._wheel.color_chosen.emit(30, 160, 90)
    assert dock._state.foreground == (30, 160, 90)
    assert (dock._r_slider.value(), dock._g_slider.value(), dock._b_slider.value()) == (30, 160, 90)


def test_a_foreground_set_elsewhere_moves_the_wheel(dock):
    dock._state.set_foreground((10, 20, 250))
    assert dock._wheel.color() == (10, 20, 250)


def test_dragging_to_grey_keeps_the_wheel_s_hue(dock):
    """A grey has no hue; echoing it back would snap the ring to red mid-drag."""
    wheel = dock._wheel
    wheel.set_color((40, 200, 40))
    hue = wheel._hue
    wheel._saturation = 0.0
    wheel._emit_color()                      # what dragging to the triangle's grey edge does
    assert dock._state.foreground == wheel.color()
    assert wheel._hue == pytest.approx(hue)


def test_a_transparent_foreground_leaves_the_wheel_alone(dock):
    dock._state.set_foreground(None)
    assert dock._wheel.color() == (200, 40, 40)
