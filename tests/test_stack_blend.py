"""Tests for statistical image stacking (mean / median / max / min)."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.stack_blend import (
    STACK_MAX,
    STACK_MEAN,
    STACK_MEDIAN,
    STACK_MIN,
    blend_stack,
    stack_images,
)


def _frame(value, h=4, w=5):
    return np.full((h, w, 3), value, dtype=np.uint8)


def test_mean_averages_frames():
    out = blend_stack([_frame(100), _frame(200)], STACK_MEAN)
    assert out.shape == (4, 5, 3)
    assert np.all(out == 150)


def test_max_takes_brightest():
    out = blend_stack([_frame(30), _frame(200), _frame(90)], STACK_MAX)
    assert np.all(out == 200)


def test_min_takes_darkest():
    out = blend_stack([_frame(30), _frame(200), _frame(90)], STACK_MIN)
    assert np.all(out == 30)


def test_median_rejects_transient():
    # A transient that appears in only one of three frames is dropped.
    base = _frame(100)
    transient = _frame(100)
    transient[0, 0] = 255
    out = blend_stack([base, transient, base], STACK_MEDIAN)
    assert out[0, 0, 0] == 100


def test_median_even_count_averages_middle():
    out = blend_stack([_frame(100), _frame(200)], STACK_MEDIAN)
    assert np.all(out == 150)


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        blend_stack([_frame(1), _frame(2)], "geometric")


def test_too_few_frames_raises():
    with pytest.raises(ValueError):
        blend_stack([_frame(1)], STACK_MEAN)


def test_mismatched_shapes_raise():
    with pytest.raises(ValueError):
        blend_stack([_frame(1, h=4), _frame(1, h=8)], STACK_MEAN)


def test_non_rgb_frame_raises():
    with pytest.raises(ValueError):
        blend_stack([np.zeros((4, 5), dtype=np.uint8)] * 2, STACK_MEAN)


def test_stack_images_returns_rgba(tmp_path):
    from PIL import Image as PILImage

    paths = []
    for i, value in enumerate((100, 200)):
        p = tmp_path / f"f{i}.png"
        PILImage.fromarray(_frame(value)).save(str(p))
        paths.append(str(p))
    out = stack_images(paths, STACK_MEAN)
    assert out.shape == (4, 5, 4)
    assert np.all(out[..., :3] == 150)
    assert np.all(out[..., 3] == 255)


def test_stack_images_too_few_raises(tmp_path):
    p = tmp_path / "only.png"
    from PIL import Image as PILImage
    PILImage.fromarray(_frame(100)).save(str(p))
    with pytest.raises(ValueError):
        stack_images([str(p)], STACK_MEAN)


def test_dialog_smoke(qapp):
    from Imervue.gui.stack_blend_dialog import StackBlendDialog
    from Imervue.image.stack_blend import STACK_MODES

    dialog = StackBlendDialog(object())
    try:
        assert dialog._mode_combo.count() == len(STACK_MODES)
        assert dialog._mode_combo.currentData() in STACK_MODES
        assert dialog._collected_paths() == []
    finally:
        dialog.deleteLater()
