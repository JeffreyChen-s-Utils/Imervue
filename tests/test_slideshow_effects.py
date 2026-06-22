"""Tests for the pure slideshow transition effects."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.export.slideshow_effects import TRANSITIONS, transition_frame


def _solid(value, h=16, w=24):
    return np.full((h, w, 3), value, dtype=np.uint8)


_PREV = _solid(0)
_NEXT = _solid(255)


@pytest.mark.parametrize("name", TRANSITIONS)
def test_endpoints_are_prev_and_next(name):
    assert np.array_equal(transition_frame(_PREV, _NEXT, name, 0.0), _PREV)
    assert np.array_equal(transition_frame(_PREV, _NEXT, name, 1.0), _NEXT)


@pytest.mark.parametrize("name", TRANSITIONS)
def test_output_shape_and_dtype_preserved(name):
    out = transition_frame(_PREV, _NEXT, name, 0.5)
    assert out.shape == _PREV.shape
    assert out.dtype == np.uint8


def test_progress_is_clamped():
    assert np.array_equal(transition_frame(_PREV, _NEXT, "fade", -1.0), _PREV)
    assert np.array_equal(transition_frame(_PREV, _NEXT, "fade", 2.0), _NEXT)


def test_fade_is_linear_midpoint():
    mid = transition_frame(_PREV, _NEXT, "fade", 0.5)
    assert mid.mean() == pytest.approx(127, abs=1)


def test_dissolve_reveals_a_fraction_of_pixels():
    out = transition_frame(_PREV, _NEXT, "dissolve", 0.5)
    revealed = np.mean(out == 255)
    # Roughly half the pixels switched to the next frame (ordered dither).
    assert 0.3 < revealed < 0.7


def test_dissolve_is_stable_between_frames():
    # A pixel revealed at progress 0.4 stays revealed at 0.6 (no flicker).
    early = transition_frame(_PREV, _NEXT, "dissolve", 0.4)
    late = transition_frame(_PREV, _NEXT, "dissolve", 0.6)
    assert np.all((early == 255) <= (late == 255))


def test_slide_left_pushes_next_in_from_the_right():
    prev = _solid(10, h=4, w=10)
    nxt = _solid(200, h=4, w=10)
    out = transition_frame(prev, nxt, "slide_left", 0.5)  # shifts in by 5 px
    assert np.all(out[:, :5] == 10)    # left half still the old frame
    assert np.all(out[:, 5:] == 200)   # right half is the incoming frame


def test_wipe_left_reveals_from_the_left_edge():
    prev = _solid(10, h=4, w=10)
    nxt = _solid(200, h=4, w=10)
    out = transition_frame(prev, nxt, "wipe_left", 0.3)  # splits at 3 px
    assert np.all(out[:, :3] == 200)
    assert np.all(out[:, 3:] == 10)


def test_slide_up_moves_vertically():
    prev = _solid(10, h=10, w=4)
    nxt = _solid(200, h=10, w=4)
    out = transition_frame(prev, nxt, "slide_up", 0.5)  # shifts up by 5 px
    assert np.all(out[:5] == 10)
    assert np.all(out[5:] == 200)


def test_unknown_transition_raises():
    with pytest.raises(ValueError, match="unknown transition"):
        transition_frame(_PREV, _NEXT, "swirl", 0.5)


def test_mismatched_shapes_raise():
    with pytest.raises(ValueError, match="share a shape"):
        transition_frame(_solid(0, 4, 4), _solid(0, 4, 8), "fade", 0.5)
