"""Pure-numpy tests for the rotation + warp deformer math and form
blending. No Qt fixture needed.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from puppet.deformers import (
    apply_rotation,
    apply_warp,
    blend_forms,
    default_rotation_form,
    default_warp_form,
)


# ---------------------------------------------------------------------------
# Rotation deformer
# ---------------------------------------------------------------------------


def test_rotation_with_zero_angle_is_identity():
    verts = np.array([[1.0, 0.0], [0.0, 1.0], [3.0, 4.0]], dtype=np.float64)
    out = apply_rotation(verts, {"anchor": [0.0, 0.0], "angle": 0.0})
    assert np.allclose(out, verts)


def test_rotation_90_degrees_around_origin():
    verts = np.array([[1.0, 0.0]], dtype=np.float64)
    out = apply_rotation(verts, {"anchor": [0.0, 0.0], "angle": math.pi / 2})
    # (1, 0) rotated 90° → (0, 1)
    assert out[0, 0] == pytest.approx(0.0, abs=1e-9)
    assert out[0, 1] == pytest.approx(1.0, abs=1e-9)


def test_rotation_around_offset_anchor():
    verts = np.array([[2.0, 1.0]], dtype=np.float64)
    out = apply_rotation(verts, {"anchor": [1.0, 1.0], "angle": math.pi})
    # 180° around (1, 1): (2, 1) → (0, 1)
    assert out[0, 0] == pytest.approx(0.0)
    assert out[0, 1] == pytest.approx(1.0)


def test_rotation_missing_fields_no_op():
    verts = np.array([[1.0, 2.0]], dtype=np.float64)
    out = apply_rotation(verts, {})   # no angle → identity
    assert np.allclose(out, verts)


# ---------------------------------------------------------------------------
# Warp deformer
# ---------------------------------------------------------------------------


def _identity_warp_form(rows: int = 3, cols: int = 3) -> dict:
    return default_warp_form((0.0, 0.0, 100.0, 100.0), rows=rows, cols=cols)


def test_warp_at_neutral_pose_is_identity_inside_bounds():
    form = _identity_warp_form()
    verts = np.array([
        [0.0, 0.0],
        [50.0, 50.0],
        [100.0, 100.0],
        [25.0, 75.0],
    ], dtype=np.float64)
    out = apply_warp(verts, form)
    assert np.allclose(out, verts, atol=1e-6)


def test_warp_does_not_touch_vertices_outside_bounds():
    form = _identity_warp_form()
    verts = np.array([[150.0, 150.0], [-10.0, 50.0]], dtype=np.float64)
    out = apply_warp(verts, form)
    assert np.allclose(out, verts)


def test_warp_translates_when_grid_shifts_uniformly():
    form = _identity_warp_form()
    grid = np.asarray(form["grid"]) + np.array([10.0, 0.0])
    form["grid"] = grid.tolist()
    verts = np.array([[50.0, 50.0]], dtype=np.float64)
    out = apply_warp(verts, form)
    assert out[0, 0] == pytest.approx(60.0)
    assert out[0, 1] == pytest.approx(50.0)


def test_warp_with_invalid_grid_no_op():
    verts = np.array([[10.0, 10.0]], dtype=np.float64)
    out = apply_warp(verts, {"rows": 3, "cols": 3, "grid": [[0.0]], "bounds": [0, 0, 100, 100]})
    assert np.allclose(out, verts)


def test_warp_with_missing_form_no_op():
    verts = np.array([[10.0, 10.0]], dtype=np.float64)
    out = apply_warp(verts, {})
    assert np.allclose(out, verts)


# ---------------------------------------------------------------------------
# Default form helpers
# ---------------------------------------------------------------------------


def test_default_rotation_form_carries_anchor_and_zero_angle():
    form = default_rotation_form((10.0, 20.0))
    assert form == {"anchor": [10.0, 20.0], "angle": 0.0}


def test_default_warp_form_grid_spans_bounds_at_neutral():
    form = default_warp_form((0.0, 0.0, 200.0, 100.0), rows=3, cols=5)
    grid = form["grid"]
    assert len(grid) == 3   # rows
    assert len(grid[0]) == 5   # cols
    # Top-left corner sits at bounds origin
    assert grid[0][0] == [0.0, 0.0]
    # Bottom-right corner at bounds opposite
    assert grid[-1][-1] == [200.0, 100.0]


# ---------------------------------------------------------------------------
# blend_forms
# ---------------------------------------------------------------------------


def test_blend_forms_lerps_numeric_fields():
    a = {"angle": 0.0, "scale": 1.0}
    b = {"angle": 1.0, "scale": 2.0}
    out = blend_forms(a, b, 0.25)
    assert out["angle"] == pytest.approx(0.25)
    assert out["scale"] == pytest.approx(1.25)


def test_blend_forms_clamps_at_endpoints():
    a = {"angle": 0.0}
    b = {"angle": 1.0}
    assert blend_forms(a, b, 0.0)["angle"] == pytest.approx(0.0)
    assert blend_forms(a, b, 1.0)["angle"] == pytest.approx(1.0)


def test_blend_forms_lerps_nested_lists():
    a = {"anchor": [0.0, 0.0]}
    b = {"anchor": [10.0, 20.0]}
    assert blend_forms(a, b, 0.5)["anchor"] == [5.0, 10.0]


def test_blend_forms_keeps_unmatched_keys():
    a = {"a": 1.0, "extra": "kept"}
    b = {"a": 3.0, "novel": "from_b"}
    out = blend_forms(a, b, 0.5)
    assert out["a"] == pytest.approx(2.0)
    assert out["extra"] == "kept"
    assert out["novel"] == "from_b"


def test_blend_forms_preserves_non_numeric_when_types_differ():
    a = {"label": "x"}
    b = {"label": 42}
    # non-matching numeric/non-numeric → keep a's value
    assert blend_forms(a, b, 0.5)["label"] == "x"
