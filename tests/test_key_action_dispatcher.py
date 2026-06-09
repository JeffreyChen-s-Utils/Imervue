"""Tests for the pure routing helpers in ``key_action_dispatcher``.

The dispatcher itself drives a live ``GPUImageView``; these tests cover the
table-driven mappings that decide *what* an action does, which are pure
functions and run without Qt or a GL context.
"""
from __future__ import annotations

from Imervue.gpu_image_view.key_action_dispatcher import (
    anim_speed_factor,
    color_mode_labels,
    cull_state_for,
    next_color_mode,
)


# ---------------------------------------------------------------
# next_color_mode
# ---------------------------------------------------------------
def test_next_color_mode_advances():
    assert next_color_mode(0) == 1
    assert next_color_mode(1) == 2
    assert next_color_mode(2) == 3


def test_next_color_mode_wraps_at_end():
    assert next_color_mode(3) == 0


# ---------------------------------------------------------------
# color_mode_labels
# ---------------------------------------------------------------
def test_color_mode_labels_all_indices():
    expected = [
        ("color_mode_normal", "Normal"),
        ("color_mode_grayscale", "Grayscale"),
        ("color_mode_invert", "Invert"),
        ("color_mode_sepia", "Sepia"),
    ]
    for idx, pair in enumerate(expected):
        assert color_mode_labels(idx) == pair


# ---------------------------------------------------------------
# cull_state_for
# ---------------------------------------------------------------
def test_cull_state_known_actions():
    assert cull_state_for("cull_pick") == "pick"
    assert cull_state_for("cull_reject") == "reject"
    assert cull_state_for("cull_unflag") == "unflagged"


def test_cull_state_unknown_returns_none():
    assert cull_state_for("zoom_in") is None
    assert cull_state_for("") is None


# ---------------------------------------------------------------
# anim_speed_factor
# ---------------------------------------------------------------
def test_anim_speed_factor_slower_faster():
    assert anim_speed_factor("anim_slower") == 1 / 1.5
    assert anim_speed_factor("anim_faster") == 1.5


def test_anim_speed_factor_other_actions_none():
    assert anim_speed_factor("anim_toggle") is None
    assert anim_speed_factor("anim_next") is None
    assert anim_speed_factor("nonsense") is None
