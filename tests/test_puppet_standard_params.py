"""Tests for the Cubism-standard parameter catalogue + its wiring into
``puppet_from_png``.

Pure-Python only — no Qt fixture required since the standard parameter
set is just dataclass construction. The PNG-import integration test
also lives here because the standard-params hook is the only thing
``puppet_from_png`` does differently.
"""
from __future__ import annotations

import io

import numpy as np
import pytest

from puppet.auto_mesh import puppet_from_png
from puppet.document import Parameter
from puppet.input_drivers import (
    DEFAULT_DRAG_X_PARAM,
    DEFAULT_DRAG_Y_PARAM,
    DEFAULT_EYE_PARAMS,
    DEFAULT_MOUTH_PARAM,
)
from puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_ANGLE_Z,
    PARAM_BREATH,
    PARAM_EYE_L_OPEN,
    PARAM_EYE_R_OPEN,
    PARAM_MOUTH_OPEN_Y,
    standard_parameter_ids,
    standard_parameters,
)


# ---------------------------------------------------------------------------
# standard_parameters / standard_parameter_ids
# ---------------------------------------------------------------------------


def test_standard_parameter_set_returns_parameters():
    params = standard_parameters()
    assert len(params) > 20   # the catalogue covers head/body/eye/mouth/brow/hair/breath
    assert all(isinstance(p, Parameter) for p in params)


def test_standard_parameter_ids_match_parameters_list():
    ids_from_list = tuple(p.id for p in standard_parameters())
    assert ids_from_list == standard_parameter_ids()


def test_standard_parameters_includes_all_driver_target_ids():
    """The webcam / drag / blink / lipsync drivers push into ids by
    string — if those ids aren't seeded by default, fresh PNG imports
    won't pick up the input. This test enforces that they stay in sync."""
    ids = set(standard_parameter_ids())
    for required in (
        DEFAULT_DRAG_X_PARAM, DEFAULT_DRAG_Y_PARAM,
        DEFAULT_MOUTH_PARAM,
        *DEFAULT_EYE_PARAMS,
        PARAM_ANGLE_Z, PARAM_BREATH,
    ):
        assert required in ids


def test_angle_params_use_minus_one_to_one_range():
    """Drivers emit values in ``[-1, 1]`` for angle-like params, so the
    parameter ranges have to match or the slider clamps the live input."""
    params = {p.id: p for p in standard_parameters()}
    for angle_id in (PARAM_ANGLE_X, PARAM_ANGLE_Y, PARAM_ANGLE_Z):
        p = params[angle_id]
        assert p.min == pytest.approx(-1.0)
        assert p.max == pytest.approx(1.0)
        assert p.default == pytest.approx(0.0)


def test_eye_open_defaults_to_open():
    """Eyes default open at 1.0 — closing should be the rare state, not
    the resting one."""
    params = {p.id: p for p in standard_parameters()}
    for eye_id in (PARAM_EYE_L_OPEN, PARAM_EYE_R_OPEN):
        p = params[eye_id]
        assert p.min == pytest.approx(0.0)
        assert p.max == pytest.approx(1.0)
        assert p.default == pytest.approx(1.0)


def test_mouth_and_breath_default_within_range():
    params = {p.id: p for p in standard_parameters()}
    mouth = params[PARAM_MOUTH_OPEN_Y]
    assert mouth.min <= mouth.default <= mouth.max
    breath = params[PARAM_BREATH]
    assert breath.min <= breath.default <= breath.max


def test_standard_parameters_returns_independent_instances():
    """Mutating one call's parameter list must not affect the next call —
    otherwise two documents share state."""
    first = standard_parameters()
    first[0].default = 99.0
    second = standard_parameters()
    assert second[0].default != pytest.approx(99.0)


# ---------------------------------------------------------------------------
# puppet_from_png integration
# ---------------------------------------------------------------------------


def _solid_rgba_png(h: int = 32, w: int = 32) -> bytes:
    from PIL import Image
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = 180
    arr[..., 3] = 255
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_puppet_from_png_seeds_standard_parameters_by_default():
    doc = puppet_from_png(_solid_rgba_png())
    ids = {p.id for p in doc.parameters}
    for required in (PARAM_ANGLE_X, PARAM_BREATH, *DEFAULT_EYE_PARAMS):
        assert required in ids


def test_puppet_from_png_can_skip_standard_parameters():
    doc = puppet_from_png(_solid_rgba_png(), seed_standard_parameters=False)
    assert doc.parameters == []


def test_puppet_from_png_keeps_single_drawable():
    """Adding the parameter catalogue must not perturb the drawable list."""
    doc = puppet_from_png(_solid_rgba_png())
    assert len(doc.drawables) == 1
    assert doc.drawables[0].id == "main"
