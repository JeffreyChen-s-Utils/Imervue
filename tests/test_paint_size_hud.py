"""Tests for the brush-size HUD overlay."""
from __future__ import annotations

import pytest

from Imervue.paint.size_hud import (
    DEFAULT_FADE_DURATION_S,
    SizeHudState,
    fade_curve,
    render_size_hud,
)


# ---------------------------------------------------------------------------
# SizeHudState
# ---------------------------------------------------------------------------


def test_state_starts_invisible():
    state = SizeHudState()
    assert state.alpha_at(now=0.0) == 0.0


def test_bump_sets_full_alpha_at_now():
    state = SizeHudState()
    state.bump(size=20, now=10.0)
    assert state.alpha_at(now=10.0) == 1.0


def test_alpha_decays_linearly_over_fade_duration():
    state = SizeHudState(fade_duration_s=1.0)
    state.bump(size=20, now=0.0)
    assert state.alpha_at(now=0.5) == pytest.approx(0.5)
    assert state.alpha_at(now=0.25) == pytest.approx(0.75)


def test_alpha_zero_after_fade_completes():
    state = SizeHudState(fade_duration_s=1.0)
    state.bump(size=20, now=0.0)
    assert state.alpha_at(now=1.0) == 0.0
    assert state.alpha_at(now=10.0) == 0.0


def test_bump_rejects_zero_size():
    state = SizeHudState()
    with pytest.raises(ValueError, match="size"):
        state.bump(size=0, now=0.0)


def test_bump_rejects_zero_fade_duration():
    state = SizeHudState(fade_duration_s=0.0)
    with pytest.raises(ValueError, match="fade_duration_s"):
        state.bump(size=10, now=0.0)


def test_re_bump_resets_fade():
    """Changing the size again restarts the fade timer."""
    state = SizeHudState(fade_duration_s=1.0)
    state.bump(size=10, now=0.0)
    state.bump(size=20, now=0.5)
    # Just-bumped at 0.5 → full alpha.
    assert state.alpha_at(now=0.5) == 1.0


# ---------------------------------------------------------------------------
# fade_curve standalone
# ---------------------------------------------------------------------------


def test_fade_curve_full_alpha_at_zero_elapsed():
    assert fade_curve(0.0) == 1.0


def test_fade_curve_zero_at_full_duration():
    assert fade_curve(DEFAULT_FADE_DURATION_S) == 0.0


def test_fade_curve_rejects_zero_duration():
    with pytest.raises(ValueError, match="fade_duration_s"):
        fade_curve(0.5, fade_duration_s=0.0)


def test_fade_curve_negative_elapsed_returns_full():
    assert fade_curve(-1.0) == 1.0


# ---------------------------------------------------------------------------
# render_size_hud
# ---------------------------------------------------------------------------


def test_render_returns_blank_for_zero_alpha():
    out = render_size_hud((40, 40), (20, 20), radius=10, alpha=0.0)
    assert out.shape == (40, 40, 4)
    assert (out == 0).all()


def test_render_paints_ring_at_radius():
    out = render_size_hud((40, 40), (20, 20), radius=10, alpha=1.0)
    # Pixels at distance ~10 from centre have non-zero alpha.
    assert out[20, 30, 3] > 0   # 10 px right of centre
    assert out[10, 20, 3] > 0   # 10 px above centre


def test_render_centre_is_transparent():
    """The HUD draws the radius outline, not a filled disc — the
    canvas content under the centre stays visible."""
    out = render_size_hud((40, 40), (20, 20), radius=10, alpha=1.0)
    assert out[20, 20, 3] == 0


def test_render_alpha_scales_output():
    full = render_size_hud((40, 40), (20, 20), radius=10, alpha=1.0)
    half = render_size_hud((40, 40), (20, 20), radius=10, alpha=0.5)
    full_max = int(full[..., 3].max())
    half_max = int(half[..., 3].max())
    assert half_max < full_max
    # Roughly halved within rounding tolerance.
    assert abs(half_max - full_max // 2) <= 5


def test_render_rejects_zero_canvas_size():
    with pytest.raises(ValueError, match="canvas_size"):
        render_size_hud((0, 40), (10, 10), radius=10, alpha=1.0)


def test_render_rejects_zero_radius():
    with pytest.raises(ValueError, match="radius"):
        render_size_hud((40, 40), (10, 10), radius=0, alpha=1.0)


def test_render_rejects_out_of_range_alpha():
    with pytest.raises(ValueError, match="alpha"):
        render_size_hud((40, 40), (10, 10), radius=10, alpha=1.5)


def test_render_rejects_zero_thickness():
    with pytest.raises(ValueError, match="thickness"):
        render_size_hud((40, 40), (10, 10), radius=10, alpha=1.0, thickness=0)


def test_render_thicker_band_paints_more_pixels():
    thin = render_size_hud((60, 60), (30, 30), radius=15, alpha=1.0, thickness=1)
    thick = render_size_hud((60, 60), (30, 30), radius=15, alpha=1.0, thickness=5)
    assert (thick[..., 3] > 0).sum() > (thin[..., 3] > 0).sum()
