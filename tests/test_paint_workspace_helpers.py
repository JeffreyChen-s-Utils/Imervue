"""Pure-helper unit tests for the Paint-workspace collaborator modules.

These exercise the side-effect-free logic that was extracted out of the
``PaintWorkspace`` god-object during the workspace refactor, so the
boundary / clamp / formatting behaviour is verified without constructing
a Qt widget (no GL surface, fast + deterministic).
"""
from __future__ import annotations

import pytest

from Imervue.paint.workspace_shortcuts import (
    BRUSH_SIZE_MAX,
    BRUSH_SIZE_MIN,
    clamp_brush_size,
    opacity_for_digit,
)
from Imervue.paint.workspace_status import (
    _AUTOSAVE_HOUR_SEC,
    _AUTOSAVE_JUST_NOW_SEC,
    _AUTOSAVE_MINUTE_SEC,
    _autosave_label,
)

# Format strings mirror the in-app fallbacks so the assertions read
# clearly; the production code pulls translated variants by key.
_LANG = {
    "paint_status_autosaved_just_now": "Saved just now",
    "paint_status_autosaved_seconds": "Saved {n}s ago",
    "paint_status_autosaved_minutes": "Saved {n}m ago",
    "paint_status_autosaved_hours": "Saved {n}h ago",
}


# ---- clamp_brush_size ---------------------------------------------------

def test_clamp_brush_size_happy_path():
    assert clamp_brush_size(10, 5) == 15
    assert clamp_brush_size(10, -3) == 7


def test_clamp_brush_size_clamps_to_max():
    assert clamp_brush_size(BRUSH_SIZE_MAX, 1) == BRUSH_SIZE_MAX
    assert clamp_brush_size(BRUSH_SIZE_MAX - 1, 50) == BRUSH_SIZE_MAX


def test_clamp_brush_size_clamps_to_min():
    assert clamp_brush_size(BRUSH_SIZE_MIN, -1) == BRUSH_SIZE_MIN
    assert clamp_brush_size(BRUSH_SIZE_MIN + 1, -50) == BRUSH_SIZE_MIN


def test_clamp_brush_size_boundaries_exact():
    # Just inside / on the boundary stays put; the off-by-one home.
    assert clamp_brush_size(BRUSH_SIZE_MIN + 1, -1) == BRUSH_SIZE_MIN
    assert clamp_brush_size(BRUSH_SIZE_MAX - 1, 1) == BRUSH_SIZE_MAX


def test_clamp_brush_size_zero_delta_is_identity():
    assert clamp_brush_size(42, 0) == 42


# ---- opacity_for_digit --------------------------------------------------

@pytest.mark.parametrize(
    ("digit", "expected"),
    [
        (1, 0.1),
        (2, 0.2),
        (5, 0.5),
        (9, 0.9),
        (0, 1.0),
    ],
)
def test_opacity_for_digit_mapping(digit, expected):
    assert opacity_for_digit(digit) == pytest.approx(expected)


def test_opacity_for_digit_wraps_multidigit():
    # Photoshop only sends single keystrokes; the modulo keeps a stray
    # two-digit value inside the table rather than producing >1.0.
    assert opacity_for_digit(10) == pytest.approx(1.0)
    assert opacity_for_digit(13) == pytest.approx(0.3)


def test_opacity_for_digit_range_is_bounded():
    for digit in range(10):
        opacity = opacity_for_digit(digit)
        assert 0.0 < opacity <= 1.0


# ---- _autosave_label ----------------------------------------------------

def test_autosave_label_just_now():
    assert _autosave_label(0.0, _LANG) == "Saved just now"
    assert _autosave_label(_AUTOSAVE_JUST_NOW_SEC - 0.1, _LANG) == "Saved just now"


def test_autosave_label_seconds():
    assert _autosave_label(float(_AUTOSAVE_JUST_NOW_SEC), _LANG) == "Saved 5s ago"
    assert _autosave_label(42.0, _LANG) == "Saved 42s ago"


def test_autosave_label_minutes_boundary():
    # Exactly one minute crosses into the minute bucket.
    assert _autosave_label(float(_AUTOSAVE_MINUTE_SEC), _LANG) == "Saved 1m ago"
    assert _autosave_label(125.0, _LANG) == "Saved 2m ago"


def test_autosave_label_hours_boundary():
    assert _autosave_label(float(_AUTOSAVE_HOUR_SEC), _LANG) == "Saved 1h ago"
    assert _autosave_label(7200.0, _LANG) == "Saved 2h ago"


def test_autosave_label_seconds_just_under_minute():
    just_under = float(_AUTOSAVE_MINUTE_SEC) - 0.5
    assert _autosave_label(just_under, _LANG) == "Saved 59s ago"
