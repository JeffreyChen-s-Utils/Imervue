"""Tests for the gradient rasteriser and dispatcher."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.gradient import GRADIENT_KINDS, render_gradient
from Imervue.paint.tool_dispatcher import GradientTool
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    return ts.load_tool_state()


@pytest.fixture
def canvas():
    return np.zeros((20, 20, 4), dtype=np.uint8)


# ---------------------------------------------------------------------------
# render_gradient — input validation
# ---------------------------------------------------------------------------


def test_render_gradient_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        render_gradient(sample_rgb_array, (0, 0), (10, 10), (0, 0, 0), (255, 255, 255))


def test_render_gradient_rejects_unknown_kind(canvas):
    with pytest.raises(ValueError):
        render_gradient(canvas, (0, 0), (10, 10), (0, 0, 0), (255, 255, 255), kind="warp")


def test_render_gradient_returns_false_when_start_equals_end(canvas):
    out = render_gradient(canvas, (5, 5), (5, 5), (0, 0, 0), (255, 255, 255))
    assert out is False


def test_render_gradient_rejects_selection_shape_mismatch(canvas):
    bad_sel = np.zeros((5, 5), dtype=np.bool_)
    with pytest.raises(ValueError):
        render_gradient(
            canvas, (0, 0), (10, 10), (0, 0, 0), (255, 255, 255), selection=bad_sel,
        )


# ---------------------------------------------------------------------------
# Linear gradient
# ---------------------------------------------------------------------------


def test_linear_gradient_endpoints_match_colours(canvas):
    render_gradient(
        canvas, (0, 10), (19, 10),
        fg=(255, 0, 0), bg=(0, 0, 255), kind="linear",
    )
    # x=0 column starts at fg.
    assert canvas[10, 0, 0] == 255
    # x=19 column ends at bg.
    assert canvas[10, 19, 2] == 255


def test_linear_gradient_midpoint_is_blend(canvas):
    render_gradient(
        canvas, (0, 10), (19, 10),
        fg=(0, 0, 0), bg=(200, 0, 0), kind="linear",
    )
    mid = int(canvas[10, 10, 0])
    # Halfway through the gradient → roughly half the bg value.
    assert 60 < mid < 140


def test_linear_gradient_writes_full_alpha(canvas):
    render_gradient(canvas, (0, 0), (19, 0), (0, 0, 0), (255, 255, 255))
    assert (canvas[..., 3] == 255).all()


def test_linear_gradient_reverse_flips_endpoints(canvas):
    render_gradient(
        canvas, (0, 10), (19, 10), (255, 0, 0), (0, 0, 255), reverse=True,
    )
    # Now x=0 should be bg (blue), x=19 should be fg (red).
    assert canvas[10, 0, 2] == 255
    assert canvas[10, 19, 0] == 255


# ---------------------------------------------------------------------------
# Radial / angle / diamond — sanity
# ---------------------------------------------------------------------------


def test_radial_gradient_centre_is_fg(canvas):
    render_gradient(canvas, (10, 10), (15, 10), (0, 200, 0), (0, 0, 200), kind="radial")
    assert canvas[10, 10, 1] == 200    # green dominates at centre
    assert canvas[10, 10, 2] == 0


def test_diamond_gradient_centre_is_fg(canvas):
    render_gradient(canvas, (10, 10), (15, 15), (0, 200, 0), (0, 0, 200), kind="diamond")
    assert canvas[10, 10, 1] == 200


def test_angle_gradient_runs():
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    out = render_gradient(canvas, (10, 10), (19, 10), (255, 0, 0), (0, 0, 255), kind="angle")
    assert out is True
    # Some pixels picked up red and some blue.
    assert (canvas[..., 0] > 100).any()
    assert (canvas[..., 2] > 100).any()


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_render_gradient_respects_selection(canvas):
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    render_gradient(
        canvas, (0, 10), (19, 10), (255, 0, 0), (0, 0, 255), selection=sel,
    )
    # Inside the selection: filled.
    assert canvas[10, 10, 3] == 255
    # Outside: untouched.
    assert canvas[0, 0, 3] == 0


# ---------------------------------------------------------------------------
# GradientTool dispatcher
# ---------------------------------------------------------------------------


def test_gradient_tool_press_records_start(state, canvas):
    tool = GradientTool(state, lambda: None)
    state.set_foreground((255, 0, 0))
    state.set_background((0, 0, 255))
    state.set_gradient(kind="linear")
    evt = PointerEvent(phase="press", x=0, y=10, button=1, modifiers=0, pressure=1.0)
    assert tool.handle(evt, canvas) is False


def test_gradient_tool_release_renders(state, canvas):
    tool = GradientTool(state, lambda: None)
    state.set_foreground((255, 0, 0))
    state.set_background((0, 0, 255))
    tool.handle(
        PointerEvent(phase="press", x=0, y=10, button=1, modifiers=0, pressure=1.0),
        canvas,
    )
    out = tool.handle(
        PointerEvent(phase="release", x=19, y=10, button=0, modifiers=0, pressure=1.0),
        canvas,
    )
    assert out is True
    assert canvas[10, 0, 0] == 255   # fg at start
    assert canvas[10, 19, 2] == 255  # bg at end


def test_gradient_tool_release_without_press_returns_false(state, canvas):
    tool = GradientTool(state, lambda: None)
    out = tool.handle(
        PointerEvent(phase="release", x=5, y=5, button=0, modifiers=0, pressure=1.0),
        canvas,
    )
    assert out is False


def test_gradient_tool_zero_drag_returns_false(state, canvas):
    tool = GradientTool(state, lambda: None)
    tool.handle(
        PointerEvent(phase="press", x=5, y=5, button=1, modifiers=0, pressure=1.0),
        canvas,
    )
    out = tool.handle(
        PointerEvent(phase="release", x=5, y=5, button=0, modifiers=0, pressure=1.0),
        canvas,
    )
    assert out is False


def test_gradient_tool_cancel_drops_pending_start(state, canvas):
    tool = GradientTool(state, lambda: None)
    tool.handle(
        PointerEvent(phase="press", x=0, y=10, button=1, modifiers=0, pressure=1.0),
        canvas,
    )
    tool.cancel()
    out = tool.handle(
        PointerEvent(phase="release", x=19, y=10, button=0, modifiers=0, pressure=1.0),
        canvas,
    )
    assert out is False


# ---------------------------------------------------------------------------
# ToolState gradient persistence
# ---------------------------------------------------------------------------


def test_state_default_gradient_kind_linear(state):
    assert state.gradient_kind == "linear"
    assert state.gradient_reverse is False


def test_set_gradient_persists(state):
    state.set_gradient(kind="radial", reverse=True)
    raw = user_setting_dict["paint_state"]
    assert raw["gradient_kind"] == "radial"
    assert raw["gradient_reverse"] is True


def test_set_gradient_round_trips(state):
    state.set_gradient(kind="diamond")
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.gradient_kind == "diamond"


def test_set_gradient_rejects_unknown_kind(state):
    with pytest.raises(ValueError):
        state.set_gradient(kind="rainbow")


def test_set_gradient_idempotent_returns_false(state):
    state.set_gradient(kind="radial")
    assert state.set_gradient(kind="radial") is False


def test_gradient_kinds_listed():
    assert GRADIENT_KINDS == ("linear", "radial", "angle", "diamond")


# ---------------------------------------------------------------------------
# Transparent endpoints — fade-to-transparent gradients (BG=None / FG=None)
# ---------------------------------------------------------------------------


def test_render_gradient_bg_none_fades_alpha_to_zero():
    """A foreground→None gradient must fade alpha from 255 at the
    foreground end to 0 at the (transparent) background end."""
    canvas = np.zeros((4, 16, 4), dtype=np.uint8)
    render_gradient(canvas, (0.0, 2.0), (15.0, 2.0), fg=(255, 0, 0), bg=None)
    # Start of the line is opaque red; end is fully transparent.
    assert int(canvas[2, 0, 3]) >= 250
    assert int(canvas[2, 15, 3]) == 0


def test_render_gradient_fg_none_fades_alpha_from_zero():
    canvas = np.zeros((4, 16, 4), dtype=np.uint8)
    render_gradient(canvas, (0.0, 2.0), (15.0, 2.0), fg=None, bg=(0, 0, 255))
    assert int(canvas[2, 0, 3]) == 0
    assert int(canvas[2, 15, 3]) >= 250


def test_render_gradient_both_endpoints_opaque_keeps_alpha_255():
    """Backwards-compat — when both endpoints are real colours the
    whole filled region stays fully opaque (the legacy behaviour
    before transparent endpoints were supported)."""
    canvas = np.zeros((4, 8, 4), dtype=np.uint8)
    render_gradient(canvas, (0.0, 2.0), (7.0, 2.0), fg=(255, 0, 0), bg=(0, 255, 0))
    assert (canvas[..., 3] == 255).all()
