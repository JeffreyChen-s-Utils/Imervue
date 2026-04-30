"""Tests for the text rendering helpers and the text tool dispatcher."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.text_render import (
    SIZE_MAX,
    SIZE_MIN,
    TextRenderOptions,
    composite_onto,
    render_text,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# render_text
# ---------------------------------------------------------------------------


def test_render_text_returns_rgba_uint8(qapp):
    arr = render_text(TextRenderOptions(text="Hello", size=24))
    assert arr.ndim == 3
    assert arr.shape[2] == 4
    assert arr.dtype == np.uint8


def test_render_text_empty_string_returns_zero_array(qapp):
    arr = render_text(TextRenderOptions(text="", size=24))
    assert arr.shape == (0, 0, 4)


def test_render_text_size_clamped_above_max(qapp):
    # Just verify it doesn't crash and returns a sensibly-sized buffer.
    arr = render_text(TextRenderOptions(text="A", size=SIZE_MAX + 100))
    assert arr.shape[0] > 0
    assert arr.shape[1] > 0


def test_render_text_size_clamped_below_min(qapp):
    arr = render_text(TextRenderOptions(text="A", size=SIZE_MIN - 5))
    assert arr.shape[0] > 0


def test_render_text_color_appears_in_pixels(qapp):
    arr = render_text(TextRenderOptions(
        text="X", size=48, color=(220, 30, 30),
    ))
    # Find an opaque pixel in the rendered glyph region.
    opaque = arr[..., 3] > 200
    assert opaque.any(), "render_text produced no opaque pixels"
    rgb_vals = arr[opaque][..., :3].astype(int).mean(axis=0)
    # Red channel should dominate.
    assert rgb_vals[0] > rgb_vals[1]
    assert rgb_vals[0] > rgb_vals[2]


# ---------------------------------------------------------------------------
# composite_onto
# ---------------------------------------------------------------------------


def test_composite_onto_paints_text(qapp):
    canvas = np.zeros((64, 64, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    rendered = render_text(TextRenderOptions(
        text="Hi", size=20, color=(255, 0, 0),
    ))
    composite_onto(canvas, rendered, x=10, y=20)
    # At least some pixels of canvas in the text region got red.
    region = canvas[20:20 + rendered.shape[0], 10:10 + rendered.shape[1], 0]
    assert (region > 100).any()


def test_composite_onto_clips_off_canvas(qapp):
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    rendered = render_text(TextRenderOptions(text="ABCDE", size=24))
    # Off-canvas — must not crash and must not modify pixels.
    snapshot = canvas.copy()
    composite_onto(canvas, rendered, x=200, y=200)
    np.testing.assert_array_equal(canvas, snapshot)


def test_composite_onto_respects_selection(qapp):
    canvas = np.zeros((64, 64, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    rendered = render_text(TextRenderOptions(
        text="Hi", size=24, color=(255, 0, 0),
    ))
    sel = np.zeros((64, 64), dtype=np.bool_)
    sel[30:50, 30:50] = True
    composite_onto(canvas, rendered, x=10, y=10, selection=sel)
    # Outside the selection the canvas is unchanged.
    assert canvas[5, 5, 0] == 0


def test_composite_onto_zero_size_rendered_is_noop(qapp):
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    snapshot = canvas.copy()
    composite_onto(canvas, np.empty((0, 0, 4), dtype=np.uint8), 0, 0)
    np.testing.assert_array_equal(canvas, snapshot)


def test_composite_onto_rejects_non_rgba_canvas(qapp):
    bad = np.zeros((4, 4), dtype=np.uint8)
    rendered = render_text(TextRenderOptions(text="A", size=20))
    with pytest.raises(ValueError):
        composite_onto(bad, rendered, 0, 0)


def test_composite_onto_rejects_non_rgba_rendered(qapp):
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    bad_rendered = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        composite_onto(canvas, bad_rendered, 0, 0)


def test_composite_onto_rejects_selection_shape_mismatch(qapp):
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    rendered = render_text(TextRenderOptions(text="A", size=12))
    bad_sel = np.zeros((3, 3), dtype=np.bool_)
    with pytest.raises(ValueError):
        composite_onto(canvas, rendered, 0, 0, selection=bad_sel)


# ---------------------------------------------------------------------------
# TextTool dispatcher (with monkeypatched dialog)
# ---------------------------------------------------------------------------


def test_text_tool_skips_when_dialog_cancelled(qapp, monkeypatch):
    from Imervue.paint.text_tool import TextTool

    state = ts.load_tool_state()

    class _CancelledDialog:
        def __init__(self, *a, **kw):
            pass

        def exec(self):
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Rejected

        def options(self):
            raise AssertionError("options() should not be queried on cancel")

    monkeypatch.setattr("Imervue.paint.text_tool.TextToolDialog", _CancelledDialog)
    tool = TextTool(state, lambda: None)
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    from Imervue.paint.canvas import PointerEvent
    evt = PointerEvent(phase="press", x=5, y=5, button=1, modifiers=0, pressure=1.0)
    assert tool.handle(evt, canvas) is False


def test_text_tool_renders_on_accept(qapp, monkeypatch):
    from Imervue.paint.text_tool import TextTool

    state = ts.load_tool_state()
    state.set_foreground((128, 200, 50))

    class _AcceptingDialog:
        def __init__(self, *a, **kw):
            pass

        def exec(self):
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Accepted

        def options(self):
            return TextRenderOptions(
                text="Hi", size=24, color=(255, 0, 0),
            )

    monkeypatch.setattr("Imervue.paint.text_tool.TextToolDialog", _AcceptingDialog)
    tool = TextTool(state, lambda: None)
    canvas = np.zeros((100, 100, 4), dtype=np.uint8)
    canvas[..., 3] = 255

    from Imervue.paint.canvas import PointerEvent
    evt = PointerEvent(phase="press", x=10, y=10, button=1, modifiers=0, pressure=1.0)
    assert tool.handle(evt, canvas) is True
    # Some red pixels appeared.
    assert (canvas[..., 0] > 100).any()
    # Foreground sync — the dialog colour propagated to the state.
    assert state.foreground == (255, 0, 0)


def test_text_tool_ignores_move_and_release(qapp):
    from Imervue.paint.text_tool import TextTool
    from Imervue.paint.canvas import PointerEvent

    state = ts.load_tool_state()
    tool = TextTool(state, lambda: None)
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    move = PointerEvent(phase="move", x=1, y=1, button=1, modifiers=0, pressure=1.0)
    release = PointerEvent(phase="release", x=2, y=2, button=0, modifiers=0, pressure=1.0)
    assert tool.handle(move, canvas) is False
    assert tool.handle(release, canvas) is False
