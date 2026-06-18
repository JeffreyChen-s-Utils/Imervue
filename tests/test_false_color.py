"""Tests for the false-colour exposure map."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.false_color import false_color


def _rgba(value, h=8, w=8):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_and_alpha():
    out = false_color(_rgba(128))
    assert out.shape == (8, 8, 4)
    assert np.all(out[..., 3] == 255)


def test_black_and_white_map_to_distinct_zones():
    black = false_color(_rgba(0))[0, 0, :3]
    white = false_color(_rgba(255))[0, 0, :3]
    assert not np.array_equal(black, white)
    # Clipped white is the red zone (dominant red channel).
    assert white[0] > white[1] and white[0] > white[2]


def test_uniform_input_gives_uniform_output():
    out = false_color(_rgba(60))
    assert np.all(out[..., :3] == out[0, 0, :3])


def test_monotonic_distinct_zones_across_ramp():
    ramp = np.stack([np.arange(256, dtype=np.uint8)] * 3, axis=-1)[None, :, :]
    alpha = np.full((1, 256, 1), 255, dtype=np.uint8)
    out = false_color(np.concatenate([ramp, alpha], axis=2))
    # The ramp passes through several distinct zone colours.
    unique_colors = {tuple(c) for c in out[0, :, :3]}
    assert len(unique_colors) >= 5


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        false_color(np.zeros((4, 4), dtype=np.uint8))
