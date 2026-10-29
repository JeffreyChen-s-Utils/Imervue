"""Contract tests for the paint retouch tools (``Imervue.paint.tools.retouch``).

Each stroking tool is checked against a reference stroke built from the bare
dab functions, so the pinned pixels are exact on any platform: the tool must
stamp the press point once, then every ``stroke_dab_positions`` step of each
move, with the strength, sign, tonal range and selection snapshot it took at
press. Return values, ``last_damage`` and the state after release / cancel /
leave are pinned alongside.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.blur import blur_dab
from Imervue.paint.brush_engine import (
    round_brush_kernel,
    spacing_from_brush,
    stroke_dab_positions,
)
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.damage import EMPTY, from_rect, union_rects
from Imervue.paint.dodge_burn import dodge_burn_dab
from Imervue.paint.smudge import sample_carry, smudge_dab
from Imervue.paint.sponge import sponge_dab
from Imervue.paint.tools import retouch
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _state(size=9, opacity=0.8, hardness=0.7):
    state = ts.load_tool_state()
    state.set_brush(size=size, opacity=opacity, hardness=hardness)
    return state


def _evt(phase, x, y):
    return PointerEvent(phase=phase, x=x, y=y, button=1, modifiers=0, pressure=1.0)


def _canvas(size=40):
    """A deterministic, textured opaque RGBA layer so every tool changes pixels."""
    yy, xx = np.mgrid[0:size, 0:size]
    arr = np.empty((size, size, 4), dtype=np.uint8)
    arr[..., 0] = (xx * xx * 7 + yy * 13) % 256
    arr[..., 1] = (yy * yy * 5 + xx * 11 + 40) % 256
    arr[..., 2] = (xx * yy * 3 + 90) % 256
    arr[..., 3] = 255
    return arr


def _selection(size=40):
    sel = np.zeros((size, size), dtype=np.float32)
    sel[:, : size // 2] = 1.0
    return sel


# Each case: (factory, reference dab(canvas, px, py, kernel, opacity, selection)).
_DAB_TOOLS = {
    "blur": (
        lambda st, sp: retouch._BlurTool(st, sp),
        lambda c, px, py, k, op, sel: blur_dab(
            c, px, py, k, strength=max(0.05, op), selection=sel),
    ),
    "dodge": (
        lambda st, sp: retouch._DodgeBurnTool(st, "dodge", sp),
        lambda c, px, py, k, op, sel: dodge_burn_dab(
            c, px, py, k, amount=max(0.05, op), range_mode="midtones", selection=sel),
    ),
    "burn": (
        lambda st, sp: retouch._DodgeBurnTool(st, "burn", sp),
        lambda c, px, py, k, op, sel: dodge_burn_dab(
            c, px, py, k, amount=-max(0.05, op), range_mode="midtones", selection=sel),
    ),
    "dodge_shadows": (
        lambda st, sp: retouch._DodgeBurnTool(st, "dodge", sp, range_mode="shadows"),
        lambda c, px, py, k, op, sel: dodge_burn_dab(
            c, px, py, k, amount=max(0.05, op), range_mode="shadows", selection=sel),
    ),
    "sponge": (
        lambda st, sp: retouch._SpongeTool(st, sp),
        lambda c, px, py, k, op, sel: sponge_dab(
            c, px, py, k, amount=-max(0.05, op), selection=sel),
    ),
    "sponge_saturate": (
        lambda st, sp: retouch._SpongeTool(st, sp, mode="saturate"),
        lambda c, px, py, k, op, sel: sponge_dab(
            c, px, py, k, amount=max(0.05, op), selection=sel),
    ),
}

_PATH = [(8.0, 10.0), (20.0, 14.0), (31.0, 30.0)]


def _reference_stroke(dab, canvas, state, selection, path=_PATH):
    """Replay a press / moves / release stroke with the bare dab function."""
    brush = state.brush
    kernel = round_brush_kernel(brush.size, brush.hardness)
    spacing = spacing_from_brush(brush.size, brush.hardness)
    rects = [dab(canvas, *path[0], kernel, brush.opacity, selection)]
    last = path[0]
    for point in [*path[1:], path[-1]]:
        union = (0, 0, 0, 0)
        for px, py in stroke_dab_positions(last, point, spacing):
            union = union_rects(union, dab(canvas, px, py, kernel, brush.opacity, selection))
        rects.append(union)
        last = point
    return rects


def _tool_stroke(tool, canvas, path=_PATH):
    results = [(tool.handle(_evt("press", *path[0]), canvas), tool.last_damage)]
    for point in path[1:]:
        results.append((tool.handle(_evt("move", *point), canvas), tool.last_damage))
    results.append((tool.handle(_evt("release", *path[-1]), canvas), tool.last_damage))
    return results


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
@pytest.mark.parametrize("use_selection", [False, True])
@pytest.mark.parametrize("opacity", [0.8, 0.0])
def test_dab_tool_stroke_matches_reference(name, use_selection, opacity):
    factory, dab = _DAB_TOOLS[name]
    state = _state(opacity=opacity)
    selection = _selection() if use_selection else None
    canvas, expected = _canvas(), _canvas()
    rects = _reference_stroke(dab, expected, state, selection)
    results = _tool_stroke(factory(state, lambda: selection), canvas)
    np.testing.assert_array_equal(canvas, expected)
    assert not np.array_equal(canvas, _canvas())
    press_rect = rects[0]
    assert results[0] == (press_rect[2] > 0 and press_rect[3] > 0, from_rect(press_rect))
    for (handled, damage), rect in zip(results[1:-1], rects[1:-1], strict=True):
        assert handled is (rect[2] > 0 and rect[3] > 0)
        assert damage == from_rect(rect)
    assert results[-1] == (True, from_rect(rects[-1]))


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_takes_selection_once_per_stroke(name):
    factory, _dab = _DAB_TOOLS[name]
    calls = []
    tool = factory(_state(), lambda: calls.append(1))
    canvas = _canvas()
    _tool_stroke(tool, canvas)
    assert len(calls) == 1
    _tool_stroke(tool, canvas)
    assert len(calls) == 2


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_default_selection_provider_is_none(name):
    factory, dab = _DAB_TOOLS[name]
    state = _state()
    canvas, expected = _canvas(), _canvas()
    _reference_stroke(dab, expected, state, None)
    _tool_stroke(factory(state, None), canvas)
    np.testing.assert_array_equal(canvas, expected)


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_state_after_release_and_idle_events(name):
    factory, _dab = _DAB_TOOLS[name]
    tool = factory(_state(), None)
    canvas = _canvas()
    assert tool.last_damage is EMPTY
    for phase in ("move", "release", "leave", "hover"):
        assert tool.handle(_evt(phase, 5, 5), canvas) is False
    np.testing.assert_array_equal(canvas, _canvas())
    _tool_stroke(tool, canvas)
    assert tool._active is False
    assert tool._last is None
    snapshot = canvas.copy()
    assert tool.handle(_evt("move", 12, 12), canvas) is False
    np.testing.assert_array_equal(canvas, snapshot)


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_leave_ends_stroke_like_release(name):
    factory, dab = _DAB_TOOLS[name]
    state = _state()
    canvas, expected = _canvas(), _canvas()
    rects = _reference_stroke(dab, expected, state, None, path=[(8.0, 8.0), (24.0, 20.0)])
    tool = factory(state, None)
    tool.handle(_evt("press", 8.0, 8.0), canvas)
    tool.handle(_evt("move", 24.0, 20.0), canvas)
    assert tool.handle(_evt("leave", 24.0, 20.0), canvas) is True
    assert tool.last_damage == from_rect(rects[-1])
    np.testing.assert_array_equal(canvas, expected)
    assert tool._active is False


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_cancel_resets_damage_and_stroke(name):
    factory, _dab = _DAB_TOOLS[name]
    tool = factory(_state(), None)
    canvas = _canvas()
    assert tool.handle(_evt("press", 10, 10), canvas) is True
    assert tool.last_damage is not EMPTY
    tool.cancel()
    assert tool.last_damage is EMPTY
    assert tool._active is False
    assert tool._last is None
    assert tool.handle(_evt("release", 10, 10), canvas) is False


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_off_canvas_press_reports_no_damage(name):
    factory, _dab = _DAB_TOOLS[name]
    tool = factory(_state(), None)
    canvas = _canvas()
    assert tool.handle(_evt("press", -500, -500), canvas) is False
    assert tool.last_damage is EMPTY
    assert tool._active is True
    assert tool.handle(_evt("move", -480, -500), canvas) is False
    assert tool.last_damage is EMPTY
    assert tool.handle(_evt("release", -480, -500), canvas) is True
    np.testing.assert_array_equal(canvas, _canvas())


@pytest.mark.parametrize("name", sorted(_DAB_TOOLS))
def test_dab_tool_reads_brush_at_press(name):
    """Kernel and spacing are fixed at press; a mid-stroke brush resize is ignored."""
    factory, dab = _DAB_TOOLS[name]
    state = _state(size=9)
    canvas, expected = _canvas(), _canvas()
    _reference_stroke(dab, expected, state, None, path=[(8.0, 8.0), (30.0, 20.0)])
    tool = factory(state, None)
    tool.handle(_evt("press", 8.0, 8.0), canvas)
    state.set_brush(size=25)
    tool.handle(_evt("move", 30.0, 20.0), canvas)
    tool.handle(_evt("release", 30.0, 20.0), canvas)
    np.testing.assert_array_equal(canvas, expected)


def test_dab_tool_rejects_non_rgba_canvas_after_arming():
    tool = retouch._BlurTool(_state(), None)
    with pytest.raises(ValueError, match="blur_dab expects HxWx4 uint8 RGBA"):
        tool.handle(_evt("press", 5, 5), np.zeros((10, 10, 3), dtype=np.uint8))
    assert tool._active is True


def test_dodge_burn_sign_and_range_attributes():
    state = _state()
    assert retouch._DodgeBurnTool(state, "dodge")._sign == 1.0
    assert retouch._DodgeBurnTool(state, "burn")._sign == -1.0
    assert retouch._DodgeBurnTool(state, "anything")._sign == -1.0
    assert retouch._DodgeBurnTool(state, "dodge")._range_mode == "midtones"
    assert retouch._DodgeBurnTool(state, "dodge", range_mode="highlights")._range_mode \
        == "highlights"
    assert retouch._SpongeTool(state)._sign == -1.0
    assert retouch._SpongeTool(state, mode="saturate")._sign == 1.0


def test_only_the_dab_tools_report_damage():
    """The dispatcher falls back to EMPTY via getattr for tools without damage tracking."""
    state = _state()
    assert not hasattr(retouch.GradientTool(state), "last_damage")
    assert not hasattr(retouch.SmudgeTool(state), "last_damage")
    for factory, _dab in _DAB_TOOLS.values():
        assert hasattr(factory(state, None), "last_damage")


def test_dispatcher_registers_every_retouch_tool():
    from Imervue.paint import tool_dispatcher
    disp = tool_dispatcher.ToolDispatcher(_state(), image_provider=_canvas)
    tools = disp._handlers
    assert type(tools["gradient"]) is retouch.GradientTool
    assert type(tools["smudge"]) is retouch.SmudgeTool
    assert type(tools["blur"]) is retouch._BlurTool
    assert type(tools["dodge"]) is retouch._DodgeBurnTool
    assert tools["dodge"]._sign == 1.0
    assert type(tools["burn"]) is retouch._DodgeBurnTool
    assert tools["burn"]._sign == -1.0
    assert type(tools["sponge"]) is retouch._SpongeTool
    for name in ("GradientTool", "SmudgeTool", "_BlurTool", "_DodgeBurnTool", "_SpongeTool"):
        assert getattr(tool_dispatcher, name) is getattr(retouch, name)


# ---------------------------------------------------------------------------
# Smudge
# ---------------------------------------------------------------------------


def _reference_smudge(canvas, state, selection, path):
    brush = state.brush
    kernel = round_brush_kernel(brush.size, brush.hardness)
    spacing = spacing_from_brush(brush.size, brush.hardness)
    carried = sample_carry(canvas, *path[0], kernel)
    last = path[0]
    for point in [*path[1:], path[-1]]:
        for px, py in stroke_dab_positions(last, point, spacing):
            _r, carried = smudge_dab(canvas, px, py, kernel, carried,
                                     strength=max(0.05, brush.opacity), selection=selection)
        last = point


@pytest.mark.parametrize("use_selection", [False, True])
@pytest.mark.parametrize("opacity", [0.8, 0.0])
def test_smudge_stroke_matches_reference(use_selection, opacity):
    state = _state(opacity=opacity)
    selection = _selection() if use_selection else None
    canvas, expected = _canvas(), _canvas()
    _reference_smudge(expected, state, selection, _PATH)
    tool = retouch.SmudgeTool(state, lambda: selection)
    assert tool.handle(_evt("press", *_PATH[0]), canvas) is False
    np.testing.assert_array_equal(canvas, _canvas())
    for point in _PATH[1:]:
        assert tool.handle(_evt("move", *point), canvas) is True
    assert tool.handle(_evt("release", *_PATH[-1]), canvas) is True
    np.testing.assert_array_equal(canvas, expected)
    assert (tool._active, tool._carried, tool._last) == (False, None, None)


def test_smudge_leave_cancel_and_idle_events():
    state = _state()
    tool = retouch.SmudgeTool(state)
    canvas = _canvas()
    for phase in ("move", "release", "leave"):
        assert tool.handle(_evt(phase, 5, 5), canvas) is False
    tool.handle(_evt("press", 8, 8), canvas)
    assert tool.handle(_evt("leave", 20, 20), canvas) is True
    assert (tool._active, tool._carried, tool._last) == (False, None, None)
    tool.handle(_evt("press", 8, 8), canvas)
    tool.cancel()
    assert (tool._active, tool._carried, tool._last) == (False, None, None)
    assert tool.handle(_evt("move", 20, 20), canvas) is False


def test_smudge_extend_without_carry_is_a_no_op():
    tool = retouch.SmudgeTool(_state())
    canvas = _canvas()
    tool.handle(_evt("press", 8, 8), canvas)
    tool._carried = None
    assert tool.handle(_evt("move", 20, 20), canvas) is False
    assert tool._active is True
    assert tool.handle(_evt("release", 20, 20), canvas) is True
    np.testing.assert_array_equal(canvas, _canvas())


# ---------------------------------------------------------------------------
# Gradient
# ---------------------------------------------------------------------------


def test_gradient_press_then_release_renders_fg_to_bg(monkeypatch):
    calls = []
    monkeypatch.setattr(retouch, "render_gradient",
                        lambda *a, **k: calls.append((a, k)) or True)
    state = _state()
    selection = _selection()
    tool = retouch.GradientTool(state, lambda: selection)
    canvas = _canvas()
    assert tool.handle(_evt("press", 1, 2), canvas) is False
    assert tool.handle(_evt("move", 3, 4), canvas) is False
    assert tool.handle(_evt("release", 30, 31), canvas) is True
    (args, kwargs), = calls
    assert args == (canvas, (1, 2), (30, 31))
    assert kwargs == {"fg": state.foreground, "bg": state.background,
                      "kind": state.gradient_kind, "reverse": state.gradient_reverse,
                      "repeat": state.gradient_repeat, "selection": selection}
    assert tool._start is None
    assert tool.handle(_evt("release", 30, 31), canvas) is False
    assert len(calls) == 1


def test_gradient_cancel_drops_the_start_point(monkeypatch):
    monkeypatch.setattr(retouch, "render_gradient", lambda *a, **k: True)
    tool = retouch.GradientTool(_state())
    canvas = _canvas()
    tool.handle(_evt("press", 1, 2), canvas)
    tool.cancel()
    assert tool.handle(_evt("release", 9, 9), canvas) is False


def test_gradient_uses_saved_multistop_when_named(monkeypatch):
    class _G:
        def __init__(self, name):
            self.name = name

    wanted = _G("sunset")
    monkeypatch.setattr("Imervue.paint.gradient_editor.load_gradients",
                        lambda: [_G("other"), wanted])
    calls = []
    monkeypatch.setattr(retouch, "render_multistop_gradient",
                        lambda *a, **k: calls.append((a, k)) or False)
    monkeypatch.setattr(retouch, "render_gradient",
                        lambda *a, **k: pytest.fail("fg/bg path must not run"))
    state = _state()
    state.gradient_name = "sunset"
    tool = retouch.GradientTool(state)
    canvas = _canvas()
    tool.handle(_evt("press", 0, 0), canvas)
    assert tool.handle(_evt("release", 5, 5), canvas) is False
    (args, kwargs), = calls
    assert args == (canvas, (0, 0), (5, 5), wanted)
    assert kwargs["selection"] is None


def test_saved_gradient_lookup(monkeypatch):
    monkeypatch.setattr("Imervue.paint.gradient_editor.load_gradients",
                        lambda: pytest.fail("no lookup for an empty name"))
    assert retouch._saved_gradient("") is None
    monkeypatch.setattr("Imervue.paint.gradient_editor.load_gradients", lambda: [])
    assert retouch._saved_gradient("gone") is None
