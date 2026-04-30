"""Tests for the multi-stop gradient editor + persistence."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.gradient_editor import (
    GradientStop,
    MultiStopGradient,
    build_lut,
    interpolate_at,
    load_gradients,
    render_multistop_gradient,
    save_gradients,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_multistop_gradients", None)
    yield
    user_setting_dict.pop("paint_multistop_gradients", None)


def _three_stop_gradient(name="G"):
    return MultiStopGradient(
        name=name,
        stops=(
            GradientStop(position=0.0, color=(255, 0, 0, 255)),
            GradientStop(position=0.5, color=(0, 255, 0, 255)),
            GradientStop(position=1.0, color=(0, 0, 255, 255)),
        ),
    )


# ---------------------------------------------------------------------------
# GradientStop
# ---------------------------------------------------------------------------


def test_gradient_stop_construction():
    s = GradientStop(position=0.5, color=(100, 50, 25, 255))
    assert s.position == 0.5
    assert s.color == (100, 50, 25, 255)


def test_gradient_stop_is_frozen():
    s = GradientStop(position=0.5, color=(0, 0, 0, 255))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.position = 0.3  # type: ignore[misc]


def test_gradient_stop_rejects_position_out_of_range():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        GradientStop(position=1.5, color=(0, 0, 0, 255))


def test_gradient_stop_rejects_three_tuple_color():
    with pytest.raises(ValueError, match="4-tuple"):
        GradientStop(position=0.5, color=(0, 0, 0))   # type: ignore[arg-type]


def test_gradient_stop_rejects_oversized_component():
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        GradientStop(position=0.5, color=(300, 0, 0, 255))


# ---------------------------------------------------------------------------
# MultiStopGradient
# ---------------------------------------------------------------------------


def test_multistop_construction():
    g = _three_stop_gradient()
    assert len(g.stops) == 3


def test_multistop_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        MultiStopGradient(
            name="   ",
            stops=(
                GradientStop(position=0.0, color=(0, 0, 0, 255)),
                GradientStop(position=1.0, color=(0, 0, 0, 255)),
            ),
        )


def test_multistop_rejects_single_stop():
    with pytest.raises(ValueError, match=">= 2"):
        MultiStopGradient(
            name="G",
            stops=(GradientStop(position=0.0, color=(0, 0, 0, 255)),),
        )


def test_multistop_rejects_unsorted_stops():
    with pytest.raises(ValueError, match="non-decreasing"):
        MultiStopGradient(
            name="G",
            stops=(
                GradientStop(position=0.5, color=(0, 0, 0, 255)),
                GradientStop(position=0.0, color=(0, 0, 0, 255)),
                GradientStop(position=1.0, color=(0, 0, 0, 255)),
            ),
        )


def test_multistop_rejects_non_full_range():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        MultiStopGradient(
            name="G",
            stops=(
                GradientStop(position=0.2, color=(0, 0, 0, 255)),
                GradientStop(position=0.8, color=(0, 0, 0, 255)),
            ),
        )


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def test_interpolate_at_endpoints_returns_endpoint_colors():
    g = _three_stop_gradient()
    assert interpolate_at(g, 0.0) == (255, 0, 0, 255)
    assert interpolate_at(g, 1.0) == (0, 0, 255, 255)


def test_interpolate_at_midpoint_returns_middle_stop():
    g = _three_stop_gradient()
    assert interpolate_at(g, 0.5) == (0, 255, 0, 255)


def test_interpolate_at_quarter_blends_first_pair():
    g = _three_stop_gradient()
    # Halfway between (255,0,0) and (0,255,0) = (127,127,0).
    r, gg, b, a = interpolate_at(g, 0.25)
    assert abs(r - 128) <= 1
    assert abs(gg - 128) <= 1
    assert b == 0
    assert a == 255


def test_interpolate_at_clamps_negative_input():
    g = _three_stop_gradient()
    assert interpolate_at(g, -0.5) == (255, 0, 0, 255)


def test_interpolate_at_clamps_above_one():
    g = _three_stop_gradient()
    assert interpolate_at(g, 2.0) == (0, 0, 255, 255)


# ---------------------------------------------------------------------------
# build_lut
# ---------------------------------------------------------------------------


def test_build_lut_size_and_dtype():
    g = _three_stop_gradient()
    lut = build_lut(g, steps=256)
    assert lut.shape == (256, 4)
    assert lut.dtype == np.uint8


def test_build_lut_endpoints_match_stop_colors():
    g = _three_stop_gradient()
    lut = build_lut(g, steps=256)
    assert tuple(lut[0]) == (255, 0, 0, 255)
    assert tuple(lut[-1]) == (0, 0, 255, 255)


def test_build_lut_rejects_zero_steps():
    g = _three_stop_gradient()
    with pytest.raises(ValueError, match="steps"):
        build_lut(g, steps=0)


# ---------------------------------------------------------------------------
# render_multistop_gradient
# ---------------------------------------------------------------------------


def test_render_multistop_gradient_paints_canvas():
    canvas = np.zeros((10, 100, 4), dtype=np.uint8)
    g = _three_stop_gradient()
    assert render_multistop_gradient(canvas, (0.0, 0.0), (99.0, 0.0), g) is True
    # Left edge near red, right edge near blue, middle near green.
    assert canvas[5, 0, 0] > 200
    assert canvas[5, -1, 2] > 200
    assert canvas[5, 50, 1] > 200


def test_render_multistop_gradient_zero_drag_returns_false():
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    g = _three_stop_gradient()
    assert render_multistop_gradient(canvas, (5, 5), (5, 5), g) is False


def test_render_multistop_gradient_reverse_swaps_endpoints():
    canvas_a = np.zeros((10, 100, 4), dtype=np.uint8)
    canvas_b = np.zeros((10, 100, 4), dtype=np.uint8)
    g = _three_stop_gradient()
    render_multistop_gradient(canvas_a, (0.0, 0.0), (99.0, 0.0), g)
    render_multistop_gradient(canvas_b, (0.0, 0.0), (99.0, 0.0), g, reverse=True)
    # Reverse flips left-edge red ↔ blue.
    assert canvas_a[5, 0, 0] > canvas_b[5, 0, 0]
    assert canvas_a[5, 0, 2] < canvas_b[5, 0, 2]


def test_render_multistop_gradient_rejects_unknown_kind():
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    g = _three_stop_gradient()
    with pytest.raises(ValueError, match="unknown gradient kind"):
        render_multistop_gradient(canvas, (0, 0), (5, 5), g, kind="spiral")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip():
    save_gradients([_three_stop_gradient(name="Mine")])
    loaded = load_gradients()
    assert len(loaded) == 1
    assert loaded[0].name == "Mine"


def test_load_returns_empty_when_nothing_stored():
    assert load_gradients() == []


def test_load_drops_corrupt_entries():
    user_setting_dict["paint_multistop_gradients"] = [
        {"name": "Good", "stops": [
            {"position": 0, "color": [0, 0, 0, 255]},
            {"position": 1, "color": [255, 255, 255, 255]},
        ]},
        "garbage",
        {"unrelated": "object without 'stops' or 'name'"},
        {"name": "No stops at all", "stops": []},
    ]
    loaded = load_gradients()
    # "garbage" is rejected (not a dict). The empty-stops entry has no
    # stops to pad against, so MultiStopGradient.__post_init__ fails on
    # the < 2 stops check.
    assert [g.name for g in loaded] == ["Good"]


def test_from_dict_pads_partial_coverage():
    """A persisted gradient with stops at 0.2 / 0.8 gets padded to
    [0, 0.2, 0.8, 1] so it satisfies the full-coverage invariant."""
    g = MultiStopGradient.from_dict({
        "name": "Centred",
        "stops": [
            {"position": 0.2, "color": [255, 0, 0, 255]},
            {"position": 0.8, "color": [0, 0, 255, 255]},
        ],
    })
    assert g.stops[0].position == 0.0
    assert g.stops[-1].position == 1.0
