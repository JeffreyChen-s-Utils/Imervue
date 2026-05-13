"""Tests for the ``Drawable.vertex_morphs`` schema + runtime path.

The Cubism-native conversion is exercised manually against the user's
local SDK — those tests would require a DLL that the public CI
doesn't have, so this module only covers the pure-Python schema +
linear-blend runtime that the conversion *outputs*.
"""
from __future__ import annotations

import numpy as np
import pytest

from puppet.document import Drawable, Parameter, PuppetDocument
from puppet.document_io import from_zip_bytes, to_zip_bytes
from puppet.runtime import apply_vertex_morphs, compose_all_drawables


def _drawable_with_morph(parameter: str, dmin, dmax) -> Drawable:
    return Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
        vertex_morphs=[{
            "parameter": parameter,
            "delta_at_min": dmin,
            "delta_at_max": dmax,
        }],
    )


# ---------------------------------------------------------------------------
# apply_vertex_morphs — pure linear blend
# ---------------------------------------------------------------------------


def test_morph_at_default_returns_rest():
    rest = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]], dtype=np.float64)
    morphs = [{
        "parameter": "P",
        "delta_at_min": [(-5.0, 0.0), (-5.0, 0.0), (-5.0, 0.0)],
        "delta_at_max": [(5.0, 0.0), (5.0, 0.0), (5.0, 0.0)],
    }]
    params = {"P": Parameter(id="P", min=-1.0, max=1.0, default=0.0)}
    out = apply_vertex_morphs(rest, morphs, {"P": 0.0}, params)
    assert np.allclose(out, rest)


def test_morph_at_max_applies_delta_at_max():
    rest = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]], dtype=np.float64)
    morphs = [{
        "parameter": "P",
        "delta_at_min": [(-5.0, 0.0), (-5.0, 0.0), (-5.0, 0.0)],
        "delta_at_max": [(5.0, 3.0), (5.0, 3.0), (5.0, 3.0)],
    }]
    params = {"P": Parameter(id="P", min=-1.0, max=1.0, default=0.0)}
    out = apply_vertex_morphs(rest, morphs, {"P": 1.0}, params)
    expected = rest + np.array([[5.0, 3.0], [5.0, 3.0], [5.0, 3.0]])
    assert np.allclose(out, expected)


def test_morph_at_min_applies_delta_at_min():
    rest = np.array([[0.0, 0.0], [10.0, 0.0]], dtype=np.float64)
    morphs = [{
        "parameter": "P",
        "delta_at_min": [(-2.0, -2.0), (-2.0, -2.0)],
        "delta_at_max": [(5.0, 5.0), (5.0, 5.0)],
    }]
    params = {"P": Parameter(id="P", min=-1.0, max=1.0, default=0.0)}
    out = apply_vertex_morphs(rest, morphs, {"P": -1.0}, params)
    expected = rest + np.array([[-2.0, -2.0], [-2.0, -2.0]])
    assert np.allclose(out, expected)


def test_morph_blends_linearly_between_default_and_max():
    rest = np.array([[0.0, 0.0]], dtype=np.float64)
    morphs = [{
        "parameter": "P",
        "delta_at_min": [(-10.0, 0.0)],
        "delta_at_max": [(10.0, 0.0)],
    }]
    params = {"P": Parameter(id="P", min=-1.0, max=1.0, default=0.0)}
    # At P=0.5 we're halfway between default (0) and max (1) → 50% of delta_at_max
    out = apply_vertex_morphs(rest, morphs, {"P": 0.5}, params)
    assert out[0, 0] == pytest.approx(5.0)
    assert out[0, 1] == pytest.approx(0.0)


def test_morph_clamps_out_of_range_parameter():
    rest = np.array([[0.0, 0.0]], dtype=np.float64)
    morphs = [{
        "parameter": "P",
        "delta_at_min": [(-10.0, 0.0)],
        "delta_at_max": [(10.0, 0.0)],
    }]
    params = {"P": Parameter(id="P", min=-1.0, max=1.0, default=0.0)}
    out = apply_vertex_morphs(rest, morphs, {"P": 99.0}, params)
    assert out[0, 0] == pytest.approx(10.0)
    out = apply_vertex_morphs(rest, morphs, {"P": -99.0}, params)
    assert out[0, 0] == pytest.approx(-10.0)


def test_morph_with_unknown_parameter_is_skipped():
    rest = np.array([[0.0, 0.0]], dtype=np.float64)
    morphs = [{
        "parameter": "DoesNotExist",
        "delta_at_min": [(-10.0, 0.0)],
        "delta_at_max": [(10.0, 0.0)],
    }]
    out = apply_vertex_morphs(rest, morphs, {}, {})
    assert np.allclose(out, rest)


def test_morph_with_empty_list_returns_rest_unchanged():
    rest = np.array([[1.0, 2.0]], dtype=np.float64)
    out = apply_vertex_morphs(rest, [], {}, {})
    assert np.allclose(out, rest)


def test_morph_with_none_returns_rest_unchanged():
    rest = np.array([[1.0, 2.0]], dtype=np.float64)
    out = apply_vertex_morphs(rest, None, {}, {})
    assert np.allclose(out, rest)


def test_multiple_morphs_compose_additively():
    rest = np.array([[0.0, 0.0]], dtype=np.float64)
    morphs = [
        {
            "parameter": "A",
            "delta_at_min": [(0.0, 0.0)],
            "delta_at_max": [(5.0, 0.0)],
        },
        {
            "parameter": "B",
            "delta_at_min": [(0.0, 0.0)],
            "delta_at_max": [(0.0, 3.0)],
        },
    ]
    params = {
        "A": Parameter(id="A", min=0.0, max=1.0, default=0.0),
        "B": Parameter(id="B", min=0.0, max=1.0, default=0.0),
    }
    out = apply_vertex_morphs(rest, morphs, {"A": 1.0, "B": 1.0}, params)
    assert out[0, 0] == pytest.approx(5.0)
    assert out[0, 1] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Document round-trip
# ---------------------------------------------------------------------------


def test_vertex_morphs_round_trip_through_zip():
    doc = PuppetDocument(size=(64, 64))
    doc.textures = {"textures/x.png": b""}
    doc.drawables = [_drawable_with_morph(
        "ParamAngleZ",
        dmin=[(-2.5, 1.0), (-2.5, 1.0), (-2.5, 1.0)],
        dmax=[(2.5, -1.0), (2.5, -1.0), (2.5, -1.0)],
    )]
    doc.parameters = [Parameter(id="ParamAngleZ", min=-1.0, max=1.0, default=0.0)]
    restored = from_zip_bytes(to_zip_bytes(doc))
    morph = restored.drawables[0].vertex_morphs[0]
    assert morph["parameter"] == "ParamAngleZ"
    assert morph["delta_at_min"] == [(-2.5, 1.0), (-2.5, 1.0), (-2.5, 1.0)]
    assert morph["delta_at_max"] == [(2.5, -1.0), (2.5, -1.0), (2.5, -1.0)]


def test_drawable_without_morphs_serialises_clean():
    doc = PuppetDocument(size=(64, 64))
    doc.textures = {"textures/x.png": b""}
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.drawables[0].vertex_morphs is None


# ---------------------------------------------------------------------------
# Integration with compose_all_drawables
# ---------------------------------------------------------------------------


def test_compose_all_drawables_applies_morphs_via_runtime():
    doc = PuppetDocument(size=(64, 64))
    doc.textures = {"textures/x.png": b""}
    doc.drawables = [_drawable_with_morph(
        "P",
        dmin=[(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
        dmax=[(5.0, 0.0), (5.0, 0.0), (5.0, 0.0)],
    )]
    doc.parameters = [Parameter(id="P", min=-1.0, max=1.0, default=0.0)]
    out = compose_all_drawables(doc, {"P": 1.0})
    verts = out["x"]
    # Rest x at 0/10/10 each shifted by +5
    assert verts[0, 0] == pytest.approx(5.0)
    assert verts[1, 0] == pytest.approx(15.0)
    assert verts[2, 0] == pytest.approx(15.0)
