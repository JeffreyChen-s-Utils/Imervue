"""Tests for the N-D :class:`ParameterBlend` sampler and its
round-trip through the ``.puppet`` archive IO.

Bilinear (2D, 4 corner keys) is the common Live2D case; we also cover
1D (degenerate to the existing linear keyform path), 3D (trilinear),
sparse grids (missing corner), and out-of-range clamping.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.document import (
    BlendKey,
    Drawable,
    ParameterBlend,
    PuppetDocument,
)
from Imervue.puppet.document_io import from_zip_bytes, to_zip_bytes
from Imervue.puppet.runtime import sample_blend_forms


def _bilinear_blend() -> ParameterBlend:
    return ParameterBlend(
        id="head_blend",
        parameters=["ParamAngleX", "ParamAngleY"],
        keys=[
            BlendKey(coords=[-1.0, -1.0], forms={"rot": {"angle": -1.0}}),
            BlendKey(coords=[1.0, -1.0], forms={"rot": {"angle": 1.0}}),
            BlendKey(coords=[-1.0, 1.0], forms={"rot": {"angle": 0.5}}),
            BlendKey(coords=[1.0, 1.0], forms={"rot": {"angle": 2.0}}),
        ],
    )


# ---------------------------------------------------------------------------
# sample_blend_forms — 2D
# ---------------------------------------------------------------------------


def test_corner_keys_are_returned_unchanged():
    blend = _bilinear_blend()
    out = sample_blend_forms(blend, {"ParamAngleX": -1.0, "ParamAngleY": -1.0})
    assert out["rot"]["angle"] == pytest.approx(-1.0)
    out = sample_blend_forms(blend, {"ParamAngleX": 1.0, "ParamAngleY": 1.0})
    assert out["rot"]["angle"] == pytest.approx(2.0)


def test_center_value_is_bilinear_average():
    blend = _bilinear_blend()
    out = sample_blend_forms(blend, {"ParamAngleX": 0.0, "ParamAngleY": 0.0})
    # Bilinear avg of (-1, 1, 0.5, 2) = 0.625
    assert out["rot"]["angle"] == pytest.approx(0.625)


def test_edge_value_is_linear_between_two_corners():
    blend = _bilinear_blend()
    # x = 0, y = -1 → midpoint between (-1, -1) and (1, -1) corners
    out = sample_blend_forms(blend, {"ParamAngleX": 0.0, "ParamAngleY": -1.0})
    assert out["rot"]["angle"] == pytest.approx(0.0)


def test_out_of_range_values_clamp_to_corner():
    blend = _bilinear_blend()
    out = sample_blend_forms(blend, {"ParamAngleX": 99.0, "ParamAngleY": -99.0})
    # Should clamp to (1, -1) corner with form angle = 1.0
    assert out["rot"]["angle"] == pytest.approx(1.0)


def test_missing_parameter_value_treated_as_low_edge():
    blend = _bilinear_blend()
    # No ParamAngleY supplied — sampler should fall back to the lowest
    # axis coord rather than crashing.
    out = sample_blend_forms(blend, {"ParamAngleX": -1.0})
    assert out["rot"]["angle"] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Sparse / degenerate / 3D
# ---------------------------------------------------------------------------


def test_empty_blend_returns_empty_dict():
    blend = ParameterBlend(id="x", parameters=["a", "b"], keys=[])
    assert sample_blend_forms(blend, {"a": 0.0, "b": 0.0}) == {}


def test_blend_with_no_parameters_returns_empty():
    blend = ParameterBlend(id="x", parameters=[], keys=[])
    assert sample_blend_forms(blend, {}) == {}


def test_sparse_grid_skips_missing_corner_gracefully():
    """If only 3 of 4 corners have keys, the sampler should still
    return *some* result (the 3 present corners contribute weighted),
    not raise."""
    blend = ParameterBlend(
        id="sparse",
        parameters=["a", "b"],
        keys=[
            BlendKey(coords=[0.0, 0.0], forms={"d": {"v": 0.0}}),
            BlendKey(coords=[1.0, 0.0], forms={"d": {"v": 1.0}}),
            BlendKey(coords=[0.0, 1.0], forms={"d": {"v": 2.0}}),
            # (1, 1) missing
        ],
    )
    out = sample_blend_forms(blend, {"a": 0.5, "b": 0.5})
    # Should not raise; result should be in the convex hull of the
    # 3 present corner values [0, 1, 2].
    assert 0.0 <= out["d"]["v"] <= 2.0


def test_one_dim_blend_acts_as_linear_param():
    blend = ParameterBlend(
        id="single",
        parameters=["x"],
        keys=[
            BlendKey(coords=[0.0], forms={"d": {"v": 0.0}}),
            BlendKey(coords=[1.0], forms={"d": {"v": 10.0}}),
        ],
    )
    assert sample_blend_forms(blend, {"x": 0.0})["d"]["v"] == pytest.approx(0.0)
    assert sample_blend_forms(blend, {"x": 1.0})["d"]["v"] == pytest.approx(10.0)
    assert sample_blend_forms(blend, {"x": 0.3})["d"]["v"] == pytest.approx(3.0)


def test_three_dim_blend_trilinear():
    """Three-axis blend — corner at (0,0,0) = 0, corner at (1,1,1) = 8.
    Centre sample averages to 4.0 if all 8 corners populated. We only
    populate the two extreme corners to confirm the sampler still
    handles a sparse N=3 case without crashing."""
    blend = ParameterBlend(
        id="tri",
        parameters=["a", "b", "c"],
        keys=[
            BlendKey(coords=[0.0, 0.0, 0.0], forms={"d": {"v": 0.0}}),
            BlendKey(coords=[1.0, 1.0, 1.0], forms={"d": {"v": 8.0}}),
        ],
    )
    out = sample_blend_forms(blend, {"a": 0.5, "b": 0.5, "c": 0.5})
    # Two corners contributing; result must be a real number in the
    # convex hull of [0, 8].
    assert 0.0 <= out["d"]["v"] <= 8.0


# ---------------------------------------------------------------------------
# Document IO round-trip
# ---------------------------------------------------------------------------


def _minimal_doc_with_blend() -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    doc.parameter_blends = [_bilinear_blend()]
    return doc


def test_parameter_blend_round_trips_through_zip():
    doc = _minimal_doc_with_blend()
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert len(restored.parameter_blends) == 1
    blend = restored.parameter_blends[0]
    assert blend.id == "head_blend"
    assert blend.parameters == ["ParamAngleX", "ParamAngleY"]
    assert len(blend.keys) == 4
    assert blend.keys[0].coords == [-1.0, -1.0]


def test_document_without_blends_round_trips_clean():
    """An older puppet without parameter_blends must still serialise —
    the field is optional and additive."""
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.parameter_blends == []
