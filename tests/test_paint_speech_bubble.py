"""Tests for the speech-bubble rasteriser + dispatcher tool."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.speech_bubble import (
    DEFAULT_BORDER,
    DEFAULT_FILL,
    MIN_BUBBLE_DIM,
    BubbleStyle,
    render_speech_bubble,
)
from Imervue.paint.tool_dispatcher import ToolDispatcher, _SpeechBubbleTool
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# render_speech_bubble — pure-numpy
# ---------------------------------------------------------------------------


def test_render_returns_rgba_layer_of_canvas_shape():
    layer = render_speech_bubble((64, 80), (10, 10, 30, 20))
    assert layer.shape == (64, 80, 4)
    assert layer.dtype == np.uint8


def test_render_paints_white_fill_inside_ellipse():
    layer = render_speech_bubble((40, 40), (5, 5, 30, 30))
    # Centre pixel must be opaque white fill.
    centre = tuple(layer[20, 20])
    assert centre == DEFAULT_FILL


def test_render_paints_black_border():
    layer = render_speech_bubble(
        (40, 40), (5, 5, 30, 30),
        style=BubbleStyle(border_px=2),
    )
    # The rim of the ellipse must contain at least one fully-black pixel.
    border_pixels = (
        (layer[..., 0] == 0)
        & (layer[..., 1] == 0)
        & (layer[..., 2] == 0)
        & (layer[..., 3] == 255)
    )
    assert border_pixels.any()


def test_render_with_zero_border_has_no_border_pixels():
    layer = render_speech_bubble(
        (40, 40), (5, 5, 30, 30),
        style=BubbleStyle(border_px=0),
    )
    # Every visible pixel is fill colour; no border == no black.
    visible = layer[..., 3] > 0
    assert (layer[visible, 0] == DEFAULT_FILL[0]).all()


def test_render_outside_bubble_is_fully_transparent():
    layer = render_speech_bubble((40, 40), (10, 10, 20, 20))
    # A corner of the canvas — well outside any reasonable bubble
    # bounding box — must be fully transparent.
    assert tuple(layer[0, 0]) == (0, 0, 0, 0)


def test_render_tail_extends_beyond_body():
    """Adding a tail must increase the number of opaque pixels
    relative to the same bubble without one."""
    no_tail = render_speech_bubble((80, 80), (20, 20, 30, 30))
    with_tail = render_speech_bubble(
        (80, 80), (20, 20, 30, 30), tail_to=(75, 75),
    )
    assert (with_tail[..., 3] > 0).sum() > (no_tail[..., 3] > 0).sum()


def test_render_cloud_shape_differs_from_ellipse():
    ellipse = render_speech_bubble(
        (40, 40), (4, 4, 32, 32), style=BubbleStyle(shape="ellipse"),
    )
    cloud = render_speech_bubble(
        (40, 40), (4, 4, 32, 32), style=BubbleStyle(shape="cloud"),
    )
    assert not np.array_equal(ellipse, cloud)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_render_rejects_unknown_shape():
    with pytest.raises(ValueError):
        render_speech_bubble(
            (40, 40), (4, 4, 30, 30), style=BubbleStyle(shape="diamond"),
        )


def test_render_rejects_negative_border_px():
    with pytest.raises(ValueError):
        render_speech_bubble(
            (40, 40), (4, 4, 30, 30), style=BubbleStyle(border_px=-1),
        )


def test_render_rejects_undersized_rect():
    with pytest.raises(ValueError):
        render_speech_bubble((40, 40), (0, 0, MIN_BUBBLE_DIM - 1, 30))


def test_render_rejects_zero_canvas():
    with pytest.raises(ValueError):
        render_speech_bubble((0, 40), (4, 4, 30, 30))


def test_default_border_color_is_opaque_black():
    assert DEFAULT_BORDER[3] == 255
    assert DEFAULT_BORDER[:3] == (0, 0, 0)


# ---------------------------------------------------------------------------
# Dispatcher tool
# ---------------------------------------------------------------------------


def _press(x, y):
    return PointerEvent(
        phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0,
    )


def _release(x, y):
    return PointerEvent(
        phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0,
    )


@pytest.fixture
def state():
    return ts.load_tool_state()


@pytest.fixture
def canvas():
    return np.zeros((64, 64, 4), dtype=np.uint8)


def test_tool_registered_in_dispatcher(state, canvas):
    disp = ToolDispatcher(state, image_provider=lambda: canvas)
    assert "speech_bubble" in disp._handlers  # noqa: SLF001
    assert isinstance(
        disp._handlers["speech_bubble"],  # noqa: SLF001
        _SpeechBubbleTool,
    )


def test_press_alone_does_not_paint(state, canvas):
    tool = _SpeechBubbleTool(state)
    handled = tool.handle(_press(10, 10), canvas)
    assert handled is False
    assert canvas.sum() == 0


def test_press_then_release_paints_bubble(state, canvas):
    tool = _SpeechBubbleTool(state)
    tool.handle(_press(10, 10), canvas)
    handled = tool.handle(_release(50, 40), canvas)
    assert handled is True
    # Some pixels in the bubble interior must now be opaque white.
    assert (canvas[..., 3] > 0).any()


def test_release_with_zero_drag_is_noop(state, canvas):
    tool = _SpeechBubbleTool(state)
    tool.handle(_press(20, 20), canvas)
    handled = tool.handle(_release(20, 20), canvas)
    assert handled is False
    assert canvas.sum() == 0


def test_release_without_press_is_noop(state, canvas):
    tool = _SpeechBubbleTool(state)
    handled = tool.handle(_release(30, 30), canvas)
    assert handled is False


def test_drag_off_canvas_clips_to_canvas_bounds(state, canvas):
    """Dragging beyond the canvas edge must not crash and must clip
    the bubble inside the canvas — no out-of-bounds writes."""
    tool = _SpeechBubbleTool(state)
    tool.handle(_press(40, 40), canvas)
    # Release far outside the 64×64 canvas.
    handled = tool.handle(_release(500, 500), canvas)
    assert handled is True
    # Canvas was painted somewhere inside its bounds.
    assert (canvas[..., 3] > 0).any()


def test_cancel_clears_press_state(state, canvas):
    tool = _SpeechBubbleTool(state)
    tool.handle(_press(10, 10), canvas)
    tool.cancel()
    # A subsequent release without a fresh press is a no-op.
    handled = tool.handle(_release(30, 30), canvas)
    assert handled is False


def test_leave_event_clears_press_state(state, canvas):
    tool = _SpeechBubbleTool(state)
    tool.handle(_press(10, 10), canvas)
    leave = PointerEvent(
        phase="leave", x=10, y=10, button=0, modifiers=0, pressure=0.0,
    )
    tool.handle(leave, canvas)
    handled = tool.handle(_release(40, 40), canvas)
    assert handled is False
