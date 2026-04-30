"""Tests for the color-blindness simulation helper."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.color_blindness import (
    SIMULATION_KINDS,
    matrix_for,
    simulate,
)


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_simulation_kinds_set():
    assert set(SIMULATION_KINDS) == {
        "protanopia", "deuteranopia", "tritanopia", "achromatopsia",
    }


def test_simulate_unknown_kind_raises():
    img = _solid((128, 128, 128))
    with pytest.raises(ValueError, match="unknown CVD"):
        simulate(img, "alien")


def test_simulate_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        simulate(rgb, "deuteranopia")


def test_simulate_zero_severity_returns_copy():
    img = _solid((200, 100, 50))
    out = simulate(img, "protanopia", severity=0.0)
    np.testing.assert_array_equal(out, img)
    assert out is not img   # should be a copy


def test_simulate_severity_clamped_above_one():
    img = _solid((200, 100, 50))
    out_full = simulate(img, "deuteranopia", severity=1.0)
    out_clamped = simulate(img, "deuteranopia", severity=10.0)
    np.testing.assert_array_equal(out_full, out_clamped)


def test_simulate_severity_clamped_below_zero():
    img = _solid((200, 100, 50))
    out = simulate(img, "deuteranopia", severity=-1.0)
    np.testing.assert_array_equal(out, img)


# ---------------------------------------------------------------------------
# matrix_for
# ---------------------------------------------------------------------------


def test_matrix_for_returns_3x3_float32():
    m = matrix_for("deuteranopia")
    assert m.shape == (3, 3)
    assert m.dtype == np.float32


def test_matrix_for_returns_copy():
    a = matrix_for("deuteranopia")
    b = matrix_for("deuteranopia")
    a[0, 0] = 99.0
    assert b[0, 0] != 99.0


def test_matrix_for_unknown_raises():
    with pytest.raises(ValueError, match="unknown CVD"):
        matrix_for("alien")


# ---------------------------------------------------------------------------
# Per-kind behaviour
# ---------------------------------------------------------------------------


def test_achromatopsia_produces_grayscale():
    """Pure red, green, blue all converge to equal-channel greys
    after achromatopsia simulation."""
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (200, 100, 50)]:
        img = _solid(color)
        out = simulate(img, "achromatopsia")
        r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
        assert abs(r - g) <= 1
        assert abs(g - b) <= 1


def test_deuteranopia_collapses_red_green_distinction():
    """A deuteranope confuses red and green — pure red and pure green
    should land closer to each other after simulation than the
    original 255-vs-0 channel separation."""
    red = _solid((255, 0, 0))
    green = _solid((0, 255, 0))
    out_red = simulate(red, "deuteranopia")
    out_green = simulate(green, "deuteranopia")
    diff_r = abs(int(out_red[0, 0, 0]) - int(out_green[0, 0, 0]))
    diff_g = abs(int(out_red[0, 0, 1]) - int(out_green[0, 0, 1]))
    # The original difference was 255 in each channel. After
    # simulation the gap should narrow significantly (red + green
    # become more confusable).
    assert diff_r < 200
    assert diff_g < 200


def test_protanopia_reduces_red_visibility():
    """A protanope's red sensitivity drops; pure red maps to a
    significantly less saturated colour."""
    red = _solid((255, 0, 0))
    out = simulate(red, "protanopia")
    # The red channel after simulation is well below 255.
    assert int(out[0, 0, 0]) < 200


def test_tritanopia_blue_axis_preserved_for_blue_pixel():
    """Tritanopia mainly confuses blue / yellow — pure blue still
    keeps a sizeable blue contribution; cross-talk shows up between
    blue and green axes."""
    blue = _solid((0, 0, 255))
    out = simulate(blue, "tritanopia")
    assert int(out[0, 0, 2]) > 100


def test_simulate_alpha_unchanged():
    img = _solid((200, 100, 50))
    img[..., 3] = 200
    out = simulate(img, "deuteranopia")
    assert (out[..., 3] == 200).all()


def test_simulate_severity_partial_blend_lies_between_identity_and_full():
    img = _solid((255, 0, 0))
    full = simulate(img, "deuteranopia", severity=1.0)
    half = simulate(img, "deuteranopia", severity=0.5)
    # Half-strength sim should land between original and full sim.
    orig_r = 255
    full_r = int(full[0, 0, 0])
    half_r = int(half[0, 0, 0])
    lo = min(orig_r, full_r)
    hi = max(orig_r, full_r)
    assert lo - 1 <= half_r <= hi + 1
