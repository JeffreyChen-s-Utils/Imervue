"""Tests for the calibration test-chart generator."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.test_charts import (
    CHECKER,
    GRADIENT,
    PATTERNS,
    SMPTE,
    SOLID,
    generate_chart,
)


def test_all_patterns_shape_and_alpha():
    for pattern in PATTERNS:
        out = generate_chart(pattern, 120, 80)
        assert out.shape == (80, 120, 4)
        assert np.all(out[..., 3] == 255)


def test_smpte_has_multiple_distinct_columns():
    out = generate_chart(SMPTE, 160, 40)
    top_row_colors = {tuple(c) for c in out[0, :, :3]}
    assert len(top_row_colors) >= 6


def test_gradient_is_monotonic():
    out = generate_chart(GRADIENT, 256, 4)[0, :, 0].astype(int)
    assert out[0] < out[-1]
    assert np.all(np.diff(out) >= 0)


def test_solid_is_uniform():
    out = generate_chart(SOLID, 32, 32, color=(10, 20, 30))
    assert np.all(out[..., 0] == 10)
    assert np.all(out[..., 1] == 20)
    assert np.all(out[..., 2] == 30)


def test_checker_has_two_values():
    out = generate_chart(CHECKER, 128, 128)
    assert len(np.unique(out[..., 0])) == 2


def test_unknown_pattern_raises():
    with pytest.raises(ValueError):
        generate_chart("rainbow", 100, 100)


def test_dialog_smoke(qapp):
    from Imervue.gui.test_charts_dialog import TestChartsDialog

    dialog = TestChartsDialog(object())
    try:
        assert dialog._pattern.count() == len(PATTERNS)
    finally:
        dialog.deleteLater()
