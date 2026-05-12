"""Tests for the drawable multiply-color tint."""
from __future__ import annotations

import pytest

from puppet.document import Drawable, PuppetDocument
from puppet.document_io import from_zip_bytes, to_zip_bytes
from puppet.runtime import resolve_drawable_color


def _drawable_with_tint(
    *,
    multiply_color=(1.0, 1.0, 1.0),
    multiply_color_keys=None,
) -> Drawable:
    return Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
        multiply_color=multiply_color,
        multiply_color_keys=multiply_color_keys,
    )


def test_default_drawable_returns_white_tint():
    d = _drawable_with_tint()
    assert resolve_drawable_color(d, {}) == (1.0, 1.0, 1.0)


def test_static_multiply_color_is_returned():
    d = _drawable_with_tint(multiply_color=(0.8, 0.6, 0.6))
    assert resolve_drawable_color(d, {}) == pytest.approx((0.8, 0.6, 0.6))


def test_parameter_driven_color_at_extremes():
    d = _drawable_with_tint(multiply_color_keys=[{
        "parameter": "ParamCheek",
        "stops": [
            {"value": 0.0, "color": (1.0, 1.0, 1.0)},
            {"value": 1.0, "color": (1.0, 0.6, 0.6)},
        ],
    }])
    assert resolve_drawable_color(d, {"ParamCheek": 0.0}) == pytest.approx((1.0, 1.0, 1.0))
    assert resolve_drawable_color(d, {"ParamCheek": 1.0}) == pytest.approx((1.0, 0.6, 0.6))


def test_parameter_driven_color_interpolates_midpoint():
    d = _drawable_with_tint(multiply_color_keys=[{
        "parameter": "ParamCheek",
        "stops": [
            {"value": 0.0, "color": (1.0, 1.0, 1.0)},
            {"value": 1.0, "color": (1.0, 0.0, 0.0)},
        ],
    }])
    r, g, b = resolve_drawable_color(d, {"ParamCheek": 0.5})
    assert r == pytest.approx(1.0)
    assert g == pytest.approx(0.5)
    assert b == pytest.approx(0.5)


def test_multiple_curves_multiply_channel_wise():
    d = _drawable_with_tint(multiply_color_keys=[
        {
            "parameter": "ParamA",
            "stops": [
                {"value": 0.0, "color": (1.0, 1.0, 1.0)},
                {"value": 1.0, "color": (0.5, 1.0, 1.0)},
            ],
        },
        {
            "parameter": "ParamB",
            "stops": [
                {"value": 0.0, "color": (1.0, 1.0, 1.0)},
                {"value": 1.0, "color": (1.0, 0.5, 1.0)},
            ],
        },
    ])
    r, g, b = resolve_drawable_color(d, {"ParamA": 1.0, "ParamB": 1.0})
    assert r == pytest.approx(0.5)
    assert g == pytest.approx(0.5)
    assert b == pytest.approx(1.0)


def test_static_and_curve_combine():
    d = _drawable_with_tint(
        multiply_color=(0.5, 0.5, 0.5),
        multiply_color_keys=[{
            "parameter": "P",
            "stops": [
                {"value": 0.0, "color": (1.0, 1.0, 1.0)},
                {"value": 1.0, "color": (1.0, 0.5, 1.0)},
            ],
        }],
    )
    r, g, b = resolve_drawable_color(d, {"P": 1.0})
    assert (r, g, b) == pytest.approx((0.5, 0.25, 0.5))


def test_out_of_range_parameter_clamps_to_edge_stop():
    d = _drawable_with_tint(multiply_color_keys=[{
        "parameter": "P",
        "stops": [
            {"value": 0.0, "color": (1.0, 1.0, 1.0)},
            {"value": 1.0, "color": (0.5, 0.5, 0.5)},
        ],
    }])
    assert resolve_drawable_color(d, {"P": 99.0}) == pytest.approx((0.5, 0.5, 0.5))
    assert resolve_drawable_color(d, {"P": -99.0}) == pytest.approx((1.0, 1.0, 1.0))


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_multiply_color_round_trips():
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [_drawable_with_tint(multiply_color=(0.8, 0.5, 0.5))]
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.drawables[0].multiply_color == (0.8, 0.5, 0.5)


def test_multiply_color_keys_round_trip():
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [_drawable_with_tint(multiply_color_keys=[{
        "parameter": "ParamCheek",
        "stops": [
            {"value": 0.0, "color": (1.0, 1.0, 1.0)},
            {"value": 1.0, "color": (1.0, 0.6, 0.6)},
        ],
    }])]
    restored = from_zip_bytes(to_zip_bytes(doc))
    keys = restored.drawables[0].multiply_color_keys
    assert keys is not None
    assert keys[0]["parameter"] == "ParamCheek"
    assert keys[0]["stops"][1]["color"] == (1.0, 0.6, 0.6)
