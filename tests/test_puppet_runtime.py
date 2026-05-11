"""Tests for the parameter sampler + deformer composer.

Pure-Python — no Qt fixture needed. Covers:
* parameter key interpolation (no keys / one key / clamp / linear)
* parameter merging when multiple parameters touch the same deformer
* end-to-end vertex composition from a tiny 1-drawable / 1-rotation rig
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from puppet.document import (
    Deformer,
    Drawable,
    Parameter,
    ParameterKey,
    PuppetDocument,
)
from puppet.runtime import (
    compose_all_drawables,
    compose_drawable_vertices,
    default_parameter_values,
    merge_parameter_samples,
    resolve_drawable_opacity,
    sample_parameter_forms,
)


# ---------------------------------------------------------------------------
# sample_parameter_forms
# ---------------------------------------------------------------------------


def _angle_param(keys: list[ParameterKey]) -> Parameter:
    return Parameter(
        id="ParamAngleX", min=-1.0, max=1.0, default=0.0, keys=keys,
    )


def test_sample_no_keys_returns_empty_overrides():
    p = _angle_param([])
    assert sample_parameter_forms(p, 0.5) == {}


def test_sample_single_key_always_returns_that_key():
    key = ParameterKey(value=0.0, forms={"d": {"angle": 0.5}})
    p = _angle_param([key])
    assert sample_parameter_forms(p, -10.0) == {"d": {"angle": 0.5}}
    assert sample_parameter_forms(p, 10.0) == {"d": {"angle": 0.5}}


def test_sample_clamps_to_edge_keys():
    keys = [
        ParameterKey(value=-1.0, forms={"d": {"angle": -0.5}}),
        ParameterKey(value=1.0, forms={"d": {"angle": 0.5}}),
    ]
    p = _angle_param(keys)
    assert sample_parameter_forms(p, -2.0)["d"]["angle"] == pytest.approx(-0.5)
    assert sample_parameter_forms(p, 2.0)["d"]["angle"] == pytest.approx(0.5)


def test_sample_linearly_interpolates_between_keys():
    keys = [
        ParameterKey(value=0.0, forms={"d": {"angle": 0.0}}),
        ParameterKey(value=10.0, forms={"d": {"angle": 1.0}}),
    ]
    p = Parameter(id="X", min=0.0, max=10.0, default=0.0, keys=keys)
    assert sample_parameter_forms(p, 2.5)["d"]["angle"] == pytest.approx(0.25)
    assert sample_parameter_forms(p, 7.5)["d"]["angle"] == pytest.approx(0.75)


def test_sample_picks_correct_segment_for_three_keys():
    keys = [
        ParameterKey(value=-1.0, forms={"d": {"angle": -1.0}}),
        ParameterKey(value=0.0, forms={"d": {"angle": 0.0}}),
        ParameterKey(value=1.0, forms={"d": {"angle": 2.0}}),
    ]
    p = _angle_param(keys)
    # Between key 0 and key 1
    assert sample_parameter_forms(p, -0.5)["d"]["angle"] == pytest.approx(-0.5)
    # Between key 1 and key 2
    assert sample_parameter_forms(p, 0.25)["d"]["angle"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# merge_parameter_samples
# ---------------------------------------------------------------------------


def test_merge_combines_disjoint_deformer_targets():
    p1 = Parameter(
        id="A", min=0.0, max=1.0, default=0.0,
        keys=[ParameterKey(value=1.0, forms={"d1": {"angle": 1.0}})],
    )
    p2 = Parameter(
        id="B", min=0.0, max=1.0, default=0.0,
        keys=[ParameterKey(value=1.0, forms={"d2": {"angle": -1.0}})],
    )
    doc = PuppetDocument()
    doc.parameters = [p1, p2]
    merged = merge_parameter_samples(doc, {"A": 1.0, "B": 1.0})
    assert merged["d1"] == {"angle": 1.0}
    assert merged["d2"] == {"angle": -1.0}


def test_merge_uses_later_parameter_wins_on_collision():
    p1 = Parameter(
        id="A", min=0.0, max=1.0, default=0.0,
        keys=[ParameterKey(value=1.0, forms={"d": {"angle": 1.0}})],
    )
    p2 = Parameter(
        id="B", min=0.0, max=1.0, default=0.0,
        keys=[ParameterKey(value=1.0, forms={"d": {"angle": 2.0}})],
    )
    doc = PuppetDocument()
    doc.parameters = [p1, p2]
    merged = merge_parameter_samples(doc, {"A": 1.0, "B": 1.0})
    assert merged["d"]["angle"] == pytest.approx(2.0)


def test_merge_skips_parameters_without_supplied_value():
    p = Parameter(
        id="A", min=0.0, max=1.0, default=0.0,
        keys=[ParameterKey(value=1.0, forms={"d": {"angle": 1.0}})],
    )
    doc = PuppetDocument()
    doc.parameters = [p]
    assert merge_parameter_samples(doc, {}) == {}


# ---------------------------------------------------------------------------
# compose_drawable_vertices
# ---------------------------------------------------------------------------


def _make_rig() -> PuppetDocument:
    """A puppet with one drawable and one rotation deformer driven by
    one parameter — the smallest rig that exercises every code path."""
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        Drawable(
            id="face",
            texture="textures/x.png",
            vertices=[(50.0, 0.0), (50.0, 50.0)],
            indices=[0, 1, 0],   # silly triangle, just for shape
            uvs=[(0.0, 0.0), (0.5, 0.5)],
            draw_order=0,
        ),
    ]
    doc.deformers = [
        Deformer(
            id="head_rot",
            type="rotation",
            parent=None,
            drawables=["face"],
            form={"anchor": [50.0, 50.0], "angle": 0.0},
        ),
    ]
    doc.parameters = [
        Parameter(
            id="ParamAngleX", min=-1.0, max=1.0, default=0.0,
            keys=[
                ParameterKey(value=-1.0, forms={"head_rot": {"angle": -math.pi / 2}}),
                ParameterKey(value=0.0, forms={"head_rot": {"angle": 0.0}}),
                ParameterKey(value=1.0, forms={"head_rot": {"angle": math.pi / 2}}),
            ],
        ),
    ]
    return doc


def test_compose_at_neutral_returns_authored_vertices():
    doc = _make_rig()
    overrides = merge_parameter_samples(doc, {"ParamAngleX": 0.0})
    out = compose_drawable_vertices(doc.drawables[0], doc.deformers, overrides)
    assert np.allclose(out, np.asarray(doc.drawables[0].vertices, dtype=np.float32))


def test_compose_at_max_rotates_by_90_degrees():
    doc = _make_rig()
    overrides = merge_parameter_samples(doc, {"ParamAngleX": 1.0})
    out = compose_drawable_vertices(doc.drawables[0], doc.deformers, overrides)
    # Vertex (50, 0) rotated 90° CCW around (50, 50) lands at (100, 50)
    assert out[0, 0] == pytest.approx(100.0, abs=1e-3)
    assert out[0, 1] == pytest.approx(50.0, abs=1e-3)
    # Vertex (50, 50) is the anchor → unchanged
    assert out[1, 0] == pytest.approx(50.0, abs=1e-3)
    assert out[1, 1] == pytest.approx(50.0, abs=1e-3)


def test_compose_skips_deformers_targeting_other_drawables():
    doc = _make_rig()
    # Add a second drawable not in the rotation deformer's list
    doc.drawables.append(
        Drawable(
            id="body",
            texture="textures/x.png",
            vertices=[(0.0, 0.0)],
            indices=[],
            uvs=[(0.0, 0.0)],
            draw_order=1,
        ),
    )
    overrides = merge_parameter_samples(doc, {"ParamAngleX": 1.0})
    out = compose_drawable_vertices(doc.drawables[1], doc.deformers, overrides)
    # body vertices untouched
    assert np.allclose(out, np.asarray(doc.drawables[1].vertices, dtype=np.float32))


def test_compose_all_drawables_returns_one_per_drawable():
    doc = _make_rig()
    out = compose_all_drawables(doc, {"ParamAngleX": 0.5})
    assert "face" in out
    assert out["face"].shape == (2, 2)
    assert out["face"].dtype == np.float32


# ---------------------------------------------------------------------------
# default_parameter_values
# ---------------------------------------------------------------------------


def test_default_parameter_values_picks_each_default():
    doc = PuppetDocument()
    doc.parameters = [
        Parameter(id="A", min=-1.0, max=1.0, default=0.5, keys=[]),
        Parameter(id="B", min=0.0, max=10.0, default=5.0, keys=[]),
    ]
    assert default_parameter_values(doc) == {"A": 0.5, "B": 5.0}


# ---------------------------------------------------------------------------
# bone_rotation composition (LBS path)
# ---------------------------------------------------------------------------


def _skinned_drawable(vertices, bone_weights):
    return Drawable(
        id="rig", texture="t.png",
        vertices=vertices,
        indices=list(range(len(vertices))),
        uvs=[(0.0, 0.0)] * len(vertices),
        draw_order=0,
        bone_weights=bone_weights,
    )


def test_compose_bone_rotation_applies_lbs_against_rest():
    """Two symmetric bones with equal weight rotating the same way pull
    the midpoint vertex in opposite directions; LBS-blended together
    the contributions cancel and the vertex stays at rest. Sequential
    composition of the same two rotations would NOT cancel — this is
    the correctness check that the runtime aggregates bone_rotations
    into a single LBS pass."""
    drawable = _skinned_drawable(
        [(0.0, 0.0)],
        bone_weights={"a": [0.5], "b": [0.5]},
    )
    angle = math.radians(30)
    deformers = [
        Deformer(id="a_bone", type="bone_rotation", parent=None,
                 drawables=["rig"],
                 form={"bone_id": "a", "anchor": [-1.0, 0.0],
                       "angle": angle}),
        Deformer(id="b_bone", type="bone_rotation", parent=None,
                 drawables=["rig"],
                 form={"bone_id": "b", "anchor": [1.0, 0.0],
                       "angle": angle}),
    ]
    out = compose_drawable_vertices(drawable, deformers, overrides={})
    assert out[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert out[0, 1] == pytest.approx(0.0, abs=1e-6)


def test_compose_bone_rotation_with_parameter_override_drives_angle():
    """Parameter keys override the bone_rotation deformer's angle; the
    LBS pass must read the override, not the rest form."""
    drawable = _skinned_drawable(
        [(1.0, 0.0)],
        bone_weights={"only": [1.0]},
    )
    deformers = [
        Deformer(id="only_bone", type="bone_rotation", parent=None,
                 drawables=["rig"],
                 form={"bone_id": "only", "anchor": [0.0, 0.0],
                       "angle": 0.0}),
    ]
    overrides = {"only_bone": {"angle": math.pi / 2}}
    out = compose_drawable_vertices(drawable, deformers, overrides)
    # 90° around origin: (1, 0) → (0, 1)
    assert out[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert out[0, 1] == pytest.approx(1.0, abs=1e-6)


def test_compose_bone_rotation_without_weights_leaves_rest_unchanged():
    """A drawable that has no bone_weights ignores bone_rotation
    deformers — bones never punch through unrelated drawables."""
    drawable = Drawable(
        id="rig", texture="t.png",
        vertices=[(2.0, 3.0)],
        indices=[0], uvs=[(0.0, 0.0)],
        draw_order=0, bone_weights=None,
    )
    deformers = [
        Deformer(id="b", type="bone_rotation", parent=None,
                 drawables=["rig"],
                 form={"bone_id": "any", "anchor": [0.0, 0.0],
                       "angle": math.pi}),
    ]
    out = compose_drawable_vertices(drawable, deformers, overrides={})
    assert np.allclose(out, [[2.0, 3.0]])


# ---------------------------------------------------------------------------
# resolve_drawable_opacity (parameter-driven cross-fade)
# ---------------------------------------------------------------------------


def _opacity_drawable(opacity_keys=None, opacity=1.0):
    return Drawable(
        id="d", texture="t.png",
        vertices=[(0.0, 0.0)], indices=[0], uvs=[(0.0, 0.0)],
        draw_order=0, opacity=opacity, opacity_keys=opacity_keys,
    )


def test_opacity_without_keys_returns_static_opacity():
    d = _opacity_drawable(opacity_keys=None, opacity=0.7)
    assert resolve_drawable_opacity(d, {}) == pytest.approx(0.7)


def test_opacity_clamps_static_value_into_unit_range():
    """A drawable authored with an out-of-range static opacity is
    clamped to [0, 1] so the renderer never sees absurd values."""
    above = _opacity_drawable(opacity=1.5)
    below = _opacity_drawable(opacity=-0.3)
    assert resolve_drawable_opacity(above, {}) == pytest.approx(1.0)
    assert resolve_drawable_opacity(below, {}) == pytest.approx(0.0)


def test_opacity_single_curve_clamps_below_lowest_stop():
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"swing": -5.0}) == pytest.approx(1.0)


def test_opacity_single_curve_clamps_above_highest_stop():
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"swing": 5.0}) == pytest.approx(0.0)


def test_opacity_single_curve_interpolates_linearly():
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 2.0, "alpha": 0.0},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"swing": 1.0}) == pytest.approx(0.5)
    assert resolve_drawable_opacity(d, {"swing": 0.5}) == pytest.approx(0.75)


def test_opacity_two_curves_multiply():
    """Two independent curves multiply: 0.5 × 0.4 = 0.2. This is how
    multi-parameter visibility (e.g. swing + facial expression) composes."""
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "a", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.5},
        ]},
        {"parameter": "b", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.4},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"a": 1.0, "b": 1.0}) == pytest.approx(0.2)


def test_opacity_zero_short_circuits():
    """When one curve hits zero, the result is zero regardless of the
    other curves — the renderer can skip the drawable entirely."""
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "a", "stops": [
            {"value": 0.0, "alpha": 0.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
        {"parameter": "b", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 1.0},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"a": 0.5, "b": 0.5}) == pytest.approx(0.0)


def test_opacity_missing_parameter_treated_as_zero():
    """A curve whose parameter isn't in values samples at value=0. This
    matches default_parameter_values semantics when a caller forgets to
    populate the dict."""
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 0.25},
            {"value": 1.0, "alpha": 1.0},
        ]},
    ])
    assert resolve_drawable_opacity(d, {}) == pytest.approx(0.25)


def test_opacity_multiplies_with_static_opacity():
    d = _opacity_drawable(opacity=0.5, opacity_keys=[
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.5},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"swing": 1.0}) == pytest.approx(0.25)


def test_opacity_three_stop_curve_picks_correct_segment():
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "swing", "stops": [
            {"value": -1.0, "alpha": 0.0},
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
    ])
    assert resolve_drawable_opacity(d, {"swing": -0.5}) == pytest.approx(0.5)
    assert resolve_drawable_opacity(d, {"swing": 0.5}) == pytest.approx(0.5)


def test_opacity_skips_malformed_entries():
    """Empty parameter id or empty stops are silently ignored so a
    half-authored opacity entry doesn't crash playback."""
    d = _opacity_drawable(opacity_keys=[
        {"parameter": "", "stops": [{"value": 0.0, "alpha": 0.5}]},
        {"parameter": "swing", "stops": []},
    ])
    assert resolve_drawable_opacity(d, {"swing": 1.0}) == pytest.approx(1.0)


def test_compose_layers_other_deformers_after_lbs_pass():
    """Non-bone deformers should run on top of the LBS result rather
    than against the rest vertices."""
    drawable = _skinned_drawable(
        [(1.0, 0.0)],
        bone_weights={"only": [1.0]},
    )
    deformers = [
        # LBS rotates (1, 0) by 90° around origin → (0, 1)
        Deformer(id="lbs", type="bone_rotation", parent=None,
                 drawables=["rig"],
                 form={"bone_id": "only", "anchor": [0.0, 0.0],
                       "angle": math.pi / 2}),
        # Then a normal rotation rotates by another 90° → (-1, 0)
        Deformer(id="extra", type="rotation", parent=None,
                 drawables=["rig"],
                 form={"anchor": [0.0, 0.0], "angle": math.pi / 2}),
    ]
    out = compose_drawable_vertices(drawable, deformers, overrides={})
    assert out[0, 0] == pytest.approx(-1.0, abs=1e-6)
    assert out[0, 1] == pytest.approx(0.0, abs=1e-6)
