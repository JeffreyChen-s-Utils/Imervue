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

from Imervue.puppet.document import (
    Deformer,
    Drawable,
    Parameter,
    ParameterKey,
    PuppetDocument,
)
from Imervue.puppet.runtime import (
    compose_all_drawables,
    compose_drawable_vertices,
    default_parameter_values,
    merge_parameter_samples,
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
