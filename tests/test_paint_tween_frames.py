"""Tests for animation tweening / inbetweening."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.animation import (
    Animation,
    AnimationFrame,
    tween_frames,
)
from Imervue.paint.document import PaintDocument


def _doc_with_color(rgb, h=4, w=4):
    doc = PaintDocument()
    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = rgb
    base[..., 3] = 255
    doc.load_image(base)
    return doc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_tween_frames_negative_n_raises():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    with pytest.raises(ValueError, match="n_inbetweens"):
        tween_frames(a, -1)


def test_tween_frames_zero_returns_copy():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 0)
    assert out.frame_count == 2


def test_tween_frames_empty_animation_returns_empty():
    a = Animation()
    out = tween_frames(a, 3)
    assert out.frame_count == 0


# ---------------------------------------------------------------------------
# Basic interpolation
# ---------------------------------------------------------------------------


def test_tween_two_frames_inserts_n_inbetweens():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 3)
    # 2 keys + 3 inbetweens = 5 frames.
    assert out.frame_count == 5


def test_tween_three_frames_with_two_pairs_inserts_2n():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((128, 128, 128))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 2)
    # 3 keys + 2 pairs * 2 inbetweens = 7 frames.
    assert out.frame_count == 7


def test_tween_inbetween_pixel_values_interpolate_linearly():
    """Black → white tween at midpoint should be ~128 grey."""
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 1)
    midpoint = out.frames[1].document.composite()
    assert midpoint is not None
    # t = 0.5 → ~128.
    assert abs(int(midpoint[0, 0, 0]) - 128) <= 1


def test_tween_keeps_original_keys_in_place():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((255, 0, 0))),
        AnimationFrame(_doc_with_color((0, 0, 255))),
    ])
    out = tween_frames(a, 2)
    # Frame 0 still red, last frame still blue.
    first = out.frames[0].document.composite()
    last = out.frames[-1].document.composite()
    assert tuple(first[0, 0, :3]) == (255, 0, 0)
    assert tuple(last[0, 0, :3]) == (0, 0, 255)


# ---------------------------------------------------------------------------
# key_indices
# ---------------------------------------------------------------------------


def test_tween_key_indices_subset_skips_intermediate_keys():
    """With explicit keys [0, 2], the existing frame at index 1 is
    DROPPED — only the named keys + their tween survive."""
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((100, 100, 100))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 1, key_indices=[0, 2])
    # 2 keys + 1 inbetween = 3 frames.
    assert out.frame_count == 3
    # Last frame is white (index 2 of original).
    last = out.frames[-1].document.composite()
    assert tuple(last[0, 0, :3]) == (255, 255, 255)


def test_tween_key_indices_filters_out_of_range():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 1, key_indices=[0, 1, 99])
    assert out.frame_count == 3   # keys [0, 1] + 1 tween


def test_tween_key_indices_empty_list_returns_copy():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0))),
        AnimationFrame(_doc_with_color((255, 255, 255))),
    ])
    out = tween_frames(a, 3, key_indices=[])
    # No keys to tween between → copy of input.
    assert out.frame_count == 2


# ---------------------------------------------------------------------------
# Shape mismatch
# ---------------------------------------------------------------------------


def test_tween_mismatched_shapes_raises():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0), h=4, w=4)),
        AnimationFrame(_doc_with_color((255, 255, 255), h=8, w=8)),
    ])
    with pytest.raises(ValueError, match="different shapes"):
        tween_frames(a, 1)


# ---------------------------------------------------------------------------
# Animation metadata
# ---------------------------------------------------------------------------


def test_tween_preserves_fps_and_looping():
    a = Animation(
        frames=[
            AnimationFrame(_doc_with_color((0, 0, 0))),
            AnimationFrame(_doc_with_color((255, 255, 255))),
        ],
        fps=24, looping=False,
    )
    out = tween_frames(a, 1)
    assert out.fps == 24
    assert out.looping is False


def test_tween_inbetweens_inherit_duration_from_left_key():
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((0, 0, 0)), duration_ms=200),
        AnimationFrame(_doc_with_color((255, 255, 255)), duration_ms=400),
    ])
    out = tween_frames(a, 1)
    # The inbetween at index 1 should pick up the LEFT key's duration.
    assert out.frames[1].duration_ms == 200
