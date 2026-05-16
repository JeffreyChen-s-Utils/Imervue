"""Edge-snap math for the desktop-pet window.

Pure-helper tests — no Qt, no display required. Verifies that:

* a window already exactly on an edge stays put;
* a window within ``threshold`` of an edge snaps to it;
* a window equidistant from both edges chooses the nearer-by-tie
  policy (top / left wins);
* a window past the screen edge is clamped back inside;
* zero / negative thresholds collapse to "no snap, but still
  clamp";
* both axes snap independently.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.edge_snap import (
    DEFAULT_SNAP_THRESHOLD,
    Rect,
    snap_to_screen_edges,
)


def _screen() -> Rect:
    return Rect(x=0, y=0, w=1920, h=1080)


def test_default_threshold_is_positive():
    """A regression guard so a future "fix" to the constant
    doesn't accidentally disable snapping."""
    assert DEFAULT_SNAP_THRESHOLD > 0


def test_left_edge_snap():
    win = Rect(x=10, y=400, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 0
    assert y == 400


def test_right_edge_snap():
    win = Rect(x=1920 - 320 - 10, y=400, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 1920 - 320
    assert y == 400


def test_top_edge_snap():
    win = Rect(x=400, y=15, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 400
    assert y == 0


def test_bottom_edge_snap():
    win = Rect(x=400, y=1080 - 480 - 10, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 400
    assert y == 1080 - 480


def test_corner_snap_both_axes():
    """A drag into the bottom-right corner snaps on both axes at
    once — desktop pets canonically dock at the corner."""
    win = Rect(x=1920 - 320 - 8, y=1080 - 480 - 8, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 1920 - 320
    assert y == 1080 - 480


def test_window_out_of_threshold_keeps_position():
    """The character must be free-floating when nowhere near an
    edge — otherwise the pet would always slam into the corner."""
    win = Rect(x=600, y=300, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert (x, y) == (600, 300)


def test_overshoot_past_right_edge_is_clamped():
    """A fast drag that ends past the screen edge must clamp the
    window back inside — the user can't strand the pet off-screen
    where they can't grab it again."""
    win = Rect(x=2000, y=500, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 1920 - 320
    assert y == 500


def test_overshoot_negative_x_is_clamped():
    win = Rect(x=-50, y=500, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 0
    assert y == 500


def test_zero_threshold_disables_snap_but_still_clamps():
    """Threshold ``0`` means "don't dock unless already exactly on
    the edge" — but a window past the edge still has to be brought
    back inside the screen."""
    win = Rect(x=2000, y=15, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=0)
    assert x == 1920 - 320
    # 15 is NOT exactly 0 so no snap to top; clamping rule keeps
    # the value because it's inside the screen.
    assert y == 15


def test_negative_threshold_clamped_to_zero():
    win = Rect(x=10, y=500, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=-100)
    # 10 is not exactly 0 so no snap; clamp keeps it inside.
    assert (x, y) == (10, 500)


def test_oversized_window_keeps_top_left_visible():
    """A window bigger than the screen on an axis collapses the
    clamp range to a single point — pick the low end so the
    top-left stays on screen for the user to grab."""
    win = Rect(x=200, y=100, w=2200, h=900)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 0
    assert y == 100  # height fits — y unchanged after snap


def test_axes_snap_independently():
    """One axis hugging the edge, the other in free space — only
    the close axis should dock."""
    win = Rect(x=5, y=540, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=24)
    assert x == 0
    assert y == 540


def test_offset_screen_origin():
    """Multi-monitor: a secondary screen typically has a non-zero
    origin (e.g. starts at x=1920 next to the primary). Snap must
    use the screen's own origin, not (0, 0)."""
    secondary = Rect(x=1920, y=0, w=1920, h=1080)
    win = Rect(x=1930, y=540, w=320, h=480)   # 10 px past secondary's left edge
    x, y = snap_to_screen_edges(win, secondary, threshold=24)
    assert x == 1920
    assert y == 540


@pytest.mark.parametrize("threshold", [1, 8, 24, 100])
def test_window_exactly_on_edge_stays(threshold):
    """A window already exactly on the left edge stays — and a y
    that's clear of both top and bottom edges by more than the
    largest threshold doesn't get snapped on the other axis."""
    win = Rect(x=0, y=300, w=320, h=480)
    x, y = snap_to_screen_edges(win, _screen(), threshold=threshold)
    assert x == 0
    # 300 is 300 from top and 300 from bottom-flush position
    # (1080 - 480 = 600), so the largest threshold in our matrix
    # (100) still doesn't reach either edge.
    assert y == 300
