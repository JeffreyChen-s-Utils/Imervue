"""Tests for waveform / RGB parade scopes."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.scopes import SCOPE_HEIGHT, compute_parade, compute_waveform


def _rgba(value, h=20, w=30):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_waveform_shape():
    wf = compute_waveform(_rgba(128, h=20, w=30))
    assert wf.shape == (SCOPE_HEIGHT, 30)
    assert wf.dtype == np.uint8


def test_waveform_constant_lands_at_one_level():
    # A flat mid-grey image: every column has a single bright row in the scope.
    wf = compute_waveform(_rgba(128))
    bright_rows = np.unique(np.argmax(wf, axis=0))
    assert bright_rows.size == 1


def test_white_sits_above_black_in_waveform():
    top_white = np.argmax(compute_waveform(_rgba(255)), axis=0)[0]
    top_black = np.argmax(compute_waveform(_rgba(0)), axis=0)[0]
    # Row 0 is the brightest level, so white peaks nearer the top (smaller row).
    assert top_white < top_black


def test_parade_shape_and_channel_isolation():
    img = _rgba(0)
    img[..., 0] = 255  # pure red
    parade = compute_parade(img)
    assert parade.shape == (SCOPE_HEIGHT, 30, 3)
    # Red trace is near the top; green/blue traces near the bottom.
    assert parade[:10, :, 0].sum() > parade[-10:, :, 0].sum()
    assert parade[-10:, :, 1].sum() > parade[:10, :, 1].sum()


def test_downscales_wide_image():
    wf = compute_waveform(_rgba(100, h=4, w=4000))
    assert wf.shape[1] <= 512


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        compute_waveform(np.zeros((8, 8), dtype=np.uint8))
