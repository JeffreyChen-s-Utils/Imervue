"""Public runtime contracts across sampling, composition, and cached frames."""
from __future__ import annotations

import math

import numpy as np
import pytest

from Imervue.puppet.document import (
    BlendKey,
    Deformer,
    Drawable,
    Parameter,
    ParameterBlend,
    ParameterKey,
    PuppetDocument,
)
from Imervue.puppet.runtime import (
    compose_all_drawables,
    merge_parameter_samples,
    resolve_drawable_color,
    resolve_drawable_opacity,
    sample_blend_forms,
    sample_parameter_forms,
)


def _drawable(**kwargs):
    return Drawable("mesh", "texture.png", [(1.0, 0.0)], [], [], **kwargs)


@pytest.mark.parametrize("value, expected", [
    (-2.0, 0.1), (-1.0, 0.1), (-0.5, 0.2), (0.0, 0.3),
    (0.5, 0.8), (1.0, 0.9), (2.0, 0.9), (math.nan, 0.9),
])
def test_unsorted_duplicate_keys_keep_first_interval_and_last_high_edge(value, expected):
    points = [(1.0, 0.9), (0.0, 0.3), (-1.0, 0.1), (0.0, 0.7)]
    parameter = Parameter("x", -1, 1, 0, [
        ParameterKey(v, {"rotation": {"angle": a}}) for v, a in points
    ])
    stops = [{"value": v, "alpha": a, "color": [a, a, a]} for v, a in points]
    curve = [{"parameter": "x", "stops": stops}]
    drawable = _drawable(opacity_keys=curve, multiply_color_keys=curve)
    assert sample_parameter_forms(parameter, value)["rotation"]["angle"] == pytest.approx(expected)
    assert resolve_drawable_opacity(drawable, {"x": value}) == pytest.approx(expected)
    assert resolve_drawable_color(drawable, {"x": value}) == pytest.approx((expected,) * 3)


def test_missing_blend_values_sample_low_corner_and_last_duplicate_wins():
    blend = ParameterBlend("grid", ["x", "y"], [
        BlendKey([0, 0], {"rotation": {"angle": 1}}),
        BlendKey([1, 0], {"rotation": {"angle": 2}}),
        BlendKey([0, 0], {"rotation": {"angle": 3}}),
    ])
    result = sample_blend_forms(blend, {})
    assert result == {"rotation": {"angle": 3}}
    result["rotation"]["angle"] = 9
    assert blend.keys[-1].forms["rotation"]["angle"] == 3


def test_blends_overlay_parameters_field_by_field_in_authored_order():
    document = PuppetDocument(parameters=[
        Parameter("x", 0, 1, 0, [ParameterKey(0, {"r": {"angle": 1, "anchor": [2, 3]}})]),
        Parameter("y", 0, 1, 0, [ParameterKey(0, {"r": {"angle": 2}})]),
    ], parameter_blends=[
        ParameterBlend("first", ["x"], [BlendKey([0], {"r": {"angle": 3}})]),
        ParameterBlend("last", ["y"], [BlendKey([0], {"r": {"angle": 4}})]),
    ])
    assert merge_parameter_samples(document, {"x": 0, "y": 0}) == {
        "r": {"angle": 4, "anchor": [2, 3]},
    }
    assert document.parameters[0].keys[0].forms["r"]["angle"] == 1


def test_morph_then_skin_then_parent_first_rotations_across_cached_frames():
    drawable = _drawable(
        bone_weights={"bone": [1.0]},
        vertex_morphs=[{"parameter": "x", "delta_at_max": [(1.0, 0.0)]}],
    )
    document = PuppetDocument(drawables=[drawable], parameters=[Parameter("x", -1, 1, 0)],
        deformers=[
            Deformer("child", "rotation", "parent", ["mesh"],
                     {"anchor": [1, 0], "angle": math.pi / 2}),
            Deformer("bone", "bone_rotation", None, ["mesh"],
                     {"bone_id": "bone", "angle": math.pi / 2}),
            Deformer("parent", "rotation", None, ["mesh"],
                     {"anchor": [0, 0], "angle": math.pi / 2}),
        ])
    first = compose_all_drawables(document, {"x": 1})["mesh"]
    neutral = compose_all_drawables(document, {"x": 0})["mesh"]
    repeated = compose_all_drawables(document, {"x": 1})["mesh"]
    np.testing.assert_allclose(first, [[1, -3]], atol=1e-6)
    np.testing.assert_allclose(neutral, [[1, -2]], atol=1e-6)
    np.testing.assert_array_equal(first, repeated)
    assert first.dtype == np.float32
    assert drawable.vertices == [(1.0, 0.0)]


def test_opacity_zero_does_not_evaluate_later_curve():
    drawable = _drawable(opacity_keys=[
        {"parameter": "x", "stops": [{"value": 0, "alpha": 0}]},
        {"parameter": "y", "stops": [{"value": 0, "alpha": 1}]},
    ])
    assert resolve_drawable_opacity(drawable, {"y": object()}) == 0


def test_color_preserves_static_negatives_only_when_no_curves_are_authored():
    drawable = _drawable(multiply_color=(-1, 2, 3))
    assert resolve_drawable_color(drawable, {}) == (-1, 2, 3)
    drawable.multiply_color_keys = [{"parameter": "", "stops": []}]
    assert resolve_drawable_color(drawable, {}) == (0, 2, 3)


@pytest.mark.parametrize("coordinate, value, expect_nan", [
    (math.nan, 0.0, True), (math.nan, math.nan, True),
    (math.nan, -1.0, True), (math.nan, 1.0, True),
    (0.0, math.nan, False), (0.0, -1.0, False), (0.0, 1.0, False),
])
def test_single_blend_coordinate_preserves_nonfinite_span(coordinate, value, expect_nan):
    blend = ParameterBlend("b", ["x"], [
        BlendKey([coordinate], {"r": {"angle": 1.0}}),
    ])
    angle = sample_blend_forms(blend, {"x": value})["r"]["angle"]
    if expect_nan:
        assert math.isnan(angle)
    else:
        assert angle == 1.0


def test_nan_sample_propagates_through_finite_blend_span():
    blend = ParameterBlend("b", ["x"], [
        BlendKey([-1.0], {"r": {"angle": 1.0}}),
        BlendKey([1.0], {"r": {"angle": 2.0}}),
    ])
    assert math.isnan(sample_blend_forms(blend, {"x": math.nan})["r"]["angle"])
    assert sample_blend_forms(blend, {"x": 0.0}) == {"r": {"angle": 1.5}}


@pytest.mark.parametrize("coordinates", [
    [math.nan, -1.0], [-1.0, math.nan],
    [math.nan, 1.0], [1.0, math.nan], [-1.0, math.nan, 1.0],
])
def test_nan_sample_preserves_mixed_authored_coordinate_span(coordinates):
    blend = ParameterBlend("b", ["x"], [
        BlendKey([coordinate], {"r": {"angle": float(index)}})
        for index, coordinate in enumerate(coordinates)
    ])
    assert math.isnan(sample_blend_forms(blend, {"x": math.nan})["r"]["angle"])
