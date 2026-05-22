"""Tests for the view-time CVD simulation wrapper.

The underlying matrix math lives in ``Imervue.paint.color_blindness``
and has its own test file. These tests cover the *view-mode* glue:
module-level state, the loader-hot-path short-circuit, and the
toggle-and-reload contract.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gpu_image_view import cvd_view_mode
from Imervue.gpu_image_view.cvd_view_mode import (
    VALID_MODES,
    apply_if_active,
    is_active,
    set_view_mode,
    view_mode,
    view_severity,
)


@pytest.fixture(autouse=True)
def _reset_cvd_state():
    """Each test starts and ends with simulation off — the module
    keeps singleton state and we don't want bleed between cases."""
    set_view_mode(None)
    yield
    set_view_mode(None)


def _sample_rgba(value: int = 200) -> np.ndarray:
    """8×8 solid-colour RGBA image. Plenty of pixels to detect a
    transform, small enough to keep tests fast."""
    img = np.zeros((8, 8, 4), dtype=np.uint8)
    img[..., 0] = value   # R
    img[..., 3] = 255     # A
    return img


# ---------------------------------------------------------------
# state setters / getters
# ---------------------------------------------------------------


def test_initial_state_is_off():
    """First import / clean state → no mode active. The image
    loader's hot path relies on this being the common case."""
    assert view_mode() is None
    assert is_active() is False


def test_set_view_mode_each_valid_kind():
    for kind in VALID_MODES:
        set_view_mode(kind)
        assert view_mode() == kind
        assert is_active() is True


def test_set_view_mode_none_turns_off():
    set_view_mode("deuteranopia")
    set_view_mode(None)
    assert view_mode() is None
    assert is_active() is False


def test_set_view_mode_unknown_string_disables():
    """Defensive: a typo'd menu entry must end up at OFF rather
    than at a half-set state."""
    set_view_mode("notacolorblindness")
    assert view_mode() is None


def test_set_view_mode_clamps_severity():
    set_view_mode("protanopia", severity=2.0)
    assert view_severity() == 1.0   # NOSONAR  # exact representable value asserted intentionally
    set_view_mode("protanopia", severity=-1.0)
    assert view_severity() == 0.0   # NOSONAR  # exact representable value asserted intentionally
    set_view_mode("protanopia", severity=0.4)
    assert view_severity() == pytest.approx(0.4)


def test_set_view_mode_non_numeric_severity_falls_back():
    """A misconfigured severity (string, None) → use 1.0 rather
    than crash the loader pipeline."""
    set_view_mode("protanopia", severity="banana")   # type: ignore[arg-type]  # NOSONAR  # negative-case fixture: helper must tolerate wrong type
    assert view_severity() == 1.0   # NOSONAR  # exact representable value asserted intentionally


def test_is_active_false_when_severity_is_zero():
    """severity=0 means identity transform → no point calling
    simulate. The short-circuit lives in is_active."""
    set_view_mode("protanopia", severity=0.0)
    assert is_active() is False


# ---------------------------------------------------------------
# apply_if_active
# ---------------------------------------------------------------


def test_apply_returns_original_when_off():
    """OFF mode → identity. The image-loader hot path must not
    allocate a copy when simulation is off."""
    img = _sample_rgba()
    out = apply_if_active(img)
    assert out is img


def test_apply_returns_modified_buffer_when_on():
    """ON mode → the helper returns a fresh array (the underlying
    simulate() always copies). Red pixels with protanopia must
    end up with different RGB values."""
    set_view_mode("protanopia")
    img = _sample_rgba(value=200)
    out = apply_if_active(img)
    assert out is not img
    # Protanopia matrix mixes R into G/R rows — the output R should
    # differ from the input R.
    assert out[0, 0, 0] != 200


def test_apply_achromatopsia_produces_grey():
    """Achromatopsia → R = G = B for every pixel. Sanity check
    that the wrapper actually delegates to the matrix math."""
    set_view_mode("achromatopsia")
    img = _sample_rgba(value=200)
    out = apply_if_active(img)
    assert out[0, 0, 0] == out[0, 0, 1] == out[0, 0, 2]


def test_apply_handles_wrong_shape_gracefully():
    """A non-RGBA buffer (somehow) → log + bypass, never raise.
    The image-loader pipeline catches the error before this point
    but the defensive path matters during refactors."""
    set_view_mode("protanopia")
    bad = np.zeros((8, 8, 3), dtype=np.uint8)
    out = apply_if_active(bad)
    assert out is bad   # bypass → return original


def test_apply_preserves_alpha_channel():
    """Simulation must not stomp on alpha — masks / cut-outs should
    look the same regardless of CVD mode."""
    set_view_mode("deuteranopia")
    img = _sample_rgba()
    img[..., 3] = 128   # half-transparent
    out = apply_if_active(img)
    assert (out[..., 3] == 128).all()


def test_severity_zero_with_active_mode_short_circuits():
    """severity=0 + a mode set → identity. Catches a subtle bug
    where the mode getter returns truthy but the math wouldn't
    actually change pixels."""
    set_view_mode("protanopia", severity=0.0)
    img = _sample_rgba()
    out = apply_if_active(img)
    assert out is img   # short-circuit path


def test_severity_partial_blends_toward_identity():
    """Severity 0.5 between identity and full simulation → output
    is somewhere between."""
    img = _sample_rgba(value=200)
    set_view_mode("protanopia", severity=1.0)
    full = apply_if_active(img)
    set_view_mode("protanopia", severity=0.5)
    half = apply_if_active(img)
    # 0.5 blend should land between identity (200) and full sim.
    assert min(full[0, 0, 0], 200) <= half[0, 0, 0] <= max(full[0, 0, 0], 200)


def test_valid_modes_matches_paint_module():
    """Re-export sanity — if the paint module ever adds a fifth
    mode, this test fails loud so the menu adds the new entry."""
    from Imervue.paint.color_blindness import SIMULATION_KINDS
    assert VALID_MODES == SIMULATION_KINDS


def test_module_state_is_singleton_across_calls():
    """Two unrelated callers must see the same active mode — the
    image loader and the workspace UI both consult this state."""
    set_view_mode("tritanopia")
    assert cvd_view_mode.view_mode() == "tritanopia"
    set_view_mode(None)
    assert cvd_view_mode.view_mode() is None
