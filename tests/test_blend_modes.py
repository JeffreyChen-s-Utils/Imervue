"""Tests for the shared RGB blend-mode math.

``blend_rgb`` / ``BLEND_MODES`` were extracted from a byte-for-byte copy that
lived in both ``brush_engine`` and ``compositing``; these tests pin the formula
table in one place and assert both modules re-export the same canonical object
so the two can never drift apart again.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.blend_modes import BLEND_MODES, blend_rgb


def _arr(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float64)


class TestBlendModesTable:
    def test_twelve_unique_modes(self):
        assert len(BLEND_MODES) == 12
        assert len(set(BLEND_MODES)) == 12

    def test_re_exported_object_is_shared(self):
        # The whole point of the extraction: both consumers point at the same
        # tuple, so adding a mode in one place reaches the other for free.
        from Imervue.paint.brush_engine import BLEND_MODES as ENGINE_MODES
        from Imervue.paint.compositing import LAYER_BLEND_MODES
        assert ENGINE_MODES is BLEND_MODES
        assert LAYER_BLEND_MODES is BLEND_MODES


class TestBlendRgb:
    def test_normal_returns_foreground(self):
        bg, fg = _arr(0.2, 0.4, 0.6), _arr(0.1, 0.5, 0.9)
        assert blend_rgb(bg, fg, "normal") is fg

    def test_multiply(self):
        np.testing.assert_allclose(
            blend_rgb(_arr(0.5), _arr(0.4), "multiply"), _arr(0.2))

    def test_screen(self):
        np.testing.assert_allclose(
            blend_rgb(_arr(0.5), _arr(0.5), "screen"), _arr(0.75))

    def test_darken_and_lighten(self):
        bg, fg = _arr(0.3), _arr(0.7)
        np.testing.assert_allclose(blend_rgb(bg, fg, "darken"), _arr(0.3))
        np.testing.assert_allclose(blend_rgb(bg, fg, "lighten"), _arr(0.7))

    def test_overlay_both_branches(self):
        # bg <= 0.5 multiplies; bg > 0.5 screens.
        np.testing.assert_allclose(
            blend_rgb(_arr(0.25, 0.75), _arr(0.5, 0.5), "overlay"),
            _arr(0.25, 0.75))

    def test_linear_dodge_and_burn_clamp(self):
        # dodge clamps the bright overflow to 1, burn clamps the dark to 0.
        np.testing.assert_allclose(
            blend_rgb(_arr(0.6), _arr(0.6), "linear_dodge"), _arr(1.0))
        np.testing.assert_allclose(
            blend_rgb(_arr(0.3), _arr(0.3), "linear_burn"), _arr(0.0))

    def test_color_dodge_white_foreground_saturates(self):
        np.testing.assert_allclose(
            blend_rgb(_arr(0.5), _arr(1.0), "color_dodge"), _arr(1.0))

    def test_soft_light_is_identity_at_neutral_foreground(self):
        # fg == 0.5 is the neutral grey: soft-light must leave bg unchanged.
        bg = _arr(0.1, 0.5, 0.9)
        np.testing.assert_allclose(blend_rgb(bg, _arr(0.5, 0.5, 0.5),
                                             "soft_light"), bg)

    def test_every_mode_stays_in_unit_range(self):
        # Stress all 12 modes over the extremes; a correct blend never leaves
        # [0, 1] (the compositor and brush both rely on this).
        grid = _arr(0.0, 0.25, 0.5, 0.75, 1.0)
        bg, fg = np.meshgrid(grid, grid)
        for mode in BLEND_MODES:
            out = blend_rgb(bg, fg, mode)
            assert out.min() >= -1e-9
            assert out.max() <= 1.0 + 1e-9

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="unknown blend_mode"):
            blend_rgb(_arr(0.5), _arr(0.5), "nope")
