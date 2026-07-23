"""Tests for the tile-wall loading policy + spinner geometry.

Pure math (no Qt, no GL), plus a couple of ``OverlayPainter`` checks driven by
a ``SimpleNamespace`` stand-in view — the painter only reads attributes here,
so no widget is constructed and the file is safe on headless CI.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from Imervue.gpu_image_view.overlay_painter import OverlayPainter
from Imervue.gpu_image_view.tile_wall_loading import (
    SPINNER_DOT_COUNT,
    should_show_wall_loading,
    spinner_dots,
    spinner_phase,
    wall_spinner_geometry,
)


# ---------------------------------------------------------------
# should_show_wall_loading
# ---------------------------------------------------------------
def test_wall_loading_shown_while_scanning_an_empty_wall():
    assert should_show_wall_loading(True, 0, True) is True


def test_wall_loading_hidden_once_the_first_batch_lands():
    """Per-tile placeholders take over — a second spinner would be noise."""
    assert should_show_wall_loading(True, 1, True) is False


def test_wall_loading_hidden_for_an_idle_empty_folder():
    assert should_show_wall_loading(True, 0, False) is False


def test_wall_loading_hidden_outside_tile_mode():
    assert should_show_wall_loading(False, 0, True) is False


def test_wall_loading_negative_count_treated_as_empty():
    """Defensive: a bogus count can't leave the blank wall without feedback."""
    assert should_show_wall_loading(True, -3, True) is True


@pytest.mark.parametrize("grid, count, scan", [
    (1, 0, 1),
    ("yes", 0, "yes"),
])
def test_wall_loading_accepts_truthy_non_bools(grid, count, scan):
    assert should_show_wall_loading(grid, count, scan) is True


# ---------------------------------------------------------------
# spinner_phase
# ---------------------------------------------------------------
def test_spinner_phase_zero_at_period_start():
    assert spinner_phase(0.0) == pytest.approx(0.0)


def test_spinner_phase_half_period_is_pi():
    assert spinner_phase(0.5) == pytest.approx(math.pi)


def test_spinner_phase_wraps_each_period():
    assert spinner_phase(7.25) == pytest.approx(spinner_phase(0.25))


def test_spinner_phase_custom_period():
    assert spinner_phase(1.0, period_s=2.0) == pytest.approx(math.pi)


def test_spinner_phase_non_positive_period_falls_back():
    """A zero period would divide by zero; the default keeps it animating."""
    assert spinner_phase(0.5, period_s=0.0) == pytest.approx(math.pi)


# ---------------------------------------------------------------
# spinner_dots
# ---------------------------------------------------------------
def test_spinner_dots_default_count():
    assert len(spinner_dots(0.0, 0.0, 10.0, 0.0)) == SPINNER_DOT_COUNT


def test_spinner_dots_lie_on_the_orbit():
    for x, y, _r, _a in spinner_dots(100.0, 50.0, 10.0, 0.3):
        assert math.hypot(x - 100.0, y - 50.0) == pytest.approx(16.0)


def test_spinner_dots_radius_is_a_third_of_nominal():
    _x, _y, dot_radius, _a = spinner_dots(0.0, 0.0, 9.0, 0.0)[0]
    assert dot_radius == pytest.approx(3.0)


def test_spinner_dots_alpha_ramps_from_min_to_max():
    alphas = [alpha for *_xyr, alpha in spinner_dots(0.0, 0.0, 10.0, 0.0)]
    assert alphas[0] == 80
    assert alphas[-1] == 200
    assert alphas == sorted(alphas)


def test_spinner_dots_evenly_spaced():
    dots = spinner_dots(0.0, 0.0, 10.0, 0.0)
    angles = [math.atan2(y, x) % (2 * math.pi) for x, y, _r, _a in dots]
    gaps = [(angles[i + 1] - angles[i]) % (2 * math.pi) for i in range(len(angles) - 1)]
    for gap in gaps:
        assert gap == pytest.approx(2 * math.pi / SPINNER_DOT_COUNT)


def test_spinner_dots_phase_rotates_the_ring():
    first = spinner_dots(0.0, 0.0, 10.0, 0.0)[0]
    turned = spinner_dots(0.0, 0.0, 10.0, math.pi)[0]
    assert turned[0] == pytest.approx(-first[0])
    assert turned[1] == pytest.approx(-first[1], abs=1e-9)


def test_spinner_dots_single_dot_uses_max_alpha():
    """count == 1 must not divide by zero on the alpha ramp."""
    dots = spinner_dots(0.0, 0.0, 10.0, 0.0, count=1)
    assert len(dots) == 1
    assert dots[0][3] == 200


def test_spinner_dots_zero_count_is_empty():
    assert spinner_dots(0.0, 0.0, 10.0, 0.0, count=0) == []


def test_spinner_dots_negative_count_is_empty():
    assert spinner_dots(0.0, 0.0, 10.0, 0.0, count=-2) == []


def test_spinner_dots_zero_radius_collapses_to_center():
    for x, y, dot_radius, _a in spinner_dots(5.0, 7.0, 0.0, 0.0):
        assert (x, y) == pytest.approx((5.0, 7.0))
        assert dot_radius == pytest.approx(0.0)


# ---------------------------------------------------------------
# wall_spinner_geometry
# ---------------------------------------------------------------
def test_wall_spinner_is_centred():
    center_x, center_y, _r = wall_spinner_geometry(800, 600)
    assert (center_x, center_y) == pytest.approx((400.0, 300.0))


def test_wall_spinner_radius_scales_with_the_shorter_edge():
    _x, _y, radius = wall_spinner_geometry(1200, 400)
    assert radius == pytest.approx(20.0)


def test_wall_spinner_radius_clamped_low_on_a_tiny_canvas():
    _x, _y, radius = wall_spinner_geometry(40, 30)
    assert radius == pytest.approx(14.0)


def test_wall_spinner_radius_clamped_high_on_a_large_canvas():
    _x, _y, radius = wall_spinner_geometry(4000, 3000)
    assert radius == pytest.approx(34.0)


def test_wall_spinner_zero_canvas_still_yields_a_radius():
    center_x, center_y, radius = wall_spinner_geometry(0, 0)
    assert (center_x, center_y) == pytest.approx((0.0, 0.0))
    assert radius == pytest.approx(14.0)


def test_wall_spinner_negative_size_clamped_to_min_radius():
    _x, _y, radius = wall_spinner_geometry(-100, 500)
    assert radius == pytest.approx(14.0)


# ---------------------------------------------------------------
# OverlayPainter wiring
# ---------------------------------------------------------------
def _wall_view(images, *, tile_grid_mode=True, scan_active=True):
    return SimpleNamespace(
        model=SimpleNamespace(images=list(images)),
        tile_grid_mode=tile_grid_mode,
        _folder_scan_active=scan_active,
        placeholder_rects=[],
        _tile_load_times={},
        updated=[],
    )


def test_overlay_wall_loading_active_while_scanning():
    assert OverlayPainter(_wall_view([]))._wall_loading_active() is True


def test_overlay_wall_loading_inactive_once_images_arrive():
    assert OverlayPainter(_wall_view(["a.png"]))._wall_loading_active() is False


def test_overlay_wall_loading_inactive_when_scan_finished():
    view = _wall_view([], scan_active=False)
    assert OverlayPainter(view)._wall_loading_active() is False


def test_overlay_wall_loading_tolerates_a_missing_flag():
    """Older view instances without ``_folder_scan_active`` must not raise."""
    view = _wall_view([])
    del view._folder_scan_active
    assert OverlayPainter(view)._wall_loading_active() is False


def test_overlay_wall_loading_tolerates_a_missing_model():
    view = _wall_view([])
    view.model = None
    assert OverlayPainter(view)._wall_loading_active() is True


def test_tick_placeholder_repaints_for_the_wall_spinner():
    """No placeholder rects yet — the pump must still repaint the wall spinner."""
    view = _wall_view([])
    view.update = lambda: view.updated.append(True)
    OverlayPainter(view).tick_placeholder()
    assert view.updated == [True]


def test_tick_placeholder_idle_when_nothing_is_loading():
    view = _wall_view(["a.png"], scan_active=False)
    view.update = lambda: view.updated.append(True)
    OverlayPainter(view).tick_placeholder()
    assert view.updated == []
