"""Canvas orchestration contracts, exercised without constructing a GL widget."""
from __future__ import annotations

import contextlib
from types import MethodType, SimpleNamespace

import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Drawable, Expression, ExpressionParam, PoseGroup, PuppetDocument,
)


class Host(SimpleNamespace):
    """Bind production methods without requesting a native Qt surface."""

    def __getattr__(self, name):
        return MethodType(getattr(PuppetCanvas, name), self)


def parameter_host(document=True):
    calls = []
    host = Host(
        _document=PuppetDocument() if document else None,
        _parameter_values={"A": 1.0, "B": 2.0},
        _recompute_deformed_vertices=lambda: calls.append("recompute"),
        update=lambda: calls.append("update"),
    )
    return host, calls


@pytest.mark.parametrize("method", ["set_parameter_value", "set_parameter_values", "force_parameter_values"])
@pytest.mark.parametrize("case", ["equal", "changed", "unknown", "empty", "nan", "no_document"])
def test_parameter_redraw_contract(method, case):
    host, calls = parameter_host(case != "no_document")
    values = {
        "equal": {"A": 1.0}, "changed": {"A": "3"}, "unknown": {"X": object()},
        "empty": {}, "nan": {"A": float("nan")}, "no_document": {"A": object()},
    }[case]
    if method == "set_parameter_value":
        if not values:
            return
        getattr(host, method)(*next(iter(values.items())))
    else:
        getattr(host, method)(values)
    redraw = case in {"changed", "nan"} or (case == "equal" and method != "set_parameter_values")
    assert calls == (["recompute", "update"] if redraw else [])
    if case == "changed":
        assert host._parameter_values["A"] == 3.0
    if case == "nan":
        assert host._parameter_values["A"] != host._parameter_values["A"]


@pytest.mark.parametrize("method", ["set_parameter_values", "force_parameter_values"])
def test_late_conversion_failure_preserves_prior_writes_without_redraw(method):
    host, calls = parameter_host()
    with pytest.raises(TypeError):
        getattr(host, method)({"A": "3", "B": object()})
    assert host._parameter_values == {"A": 3.0, "B": 2.0}
    assert calls == []


def test_document_binding_order_and_reset():
    host, calls = parameter_host()
    document = PuppetDocument()

    @contextlib.contextmanager
    def current():
        assert host._document is document
        assert host._draw_list == []
        calls.append("current")
        yield
        calls.append("done")

    host._current_gl_context = current
    host._invalidate_texture_cache = lambda: calls.append("textures")
    host._invalidate_buffer_cache = lambda: calls.append("buffers")
    host._physics = SimpleNamespace(bind_document=lambda doc: calls.append(("bind", doc)))
    host._sync_physics_timer = lambda: calls.append("timer")
    host.document_loaded = SimpleNamespace(emit=lambda: calls.append("document"))
    host.parameters_changed = SimpleNamespace(emit=lambda: calls.append("parameters"))
    host.load_document(document)
    assert calls == ["current", "textures", "buffers", "done", ("bind", document),
                     "timer", "recompute", "document", "parameters", "update"]
    assert host._parameter_values == host._active_pose == host._physics_outputs == {}
    assert host._active_expressions == []
    assert host._user_view_locked is False


@pytest.mark.parametrize("failure", [None, "construct", "bind", "bind_raise", "frame", "readback", "release", "empty"])
def test_offscreen_resource_and_restore_order(monkeypatch, failure):
    from PySide6 import QtOpenGL

    globals_ = PuppetCanvas.render_offscreen_puppet.__globals__
    calls = []

    @contextlib.contextmanager
    def preserved():
        calls.append("save")
        try:
            yield
        finally:
            calls.append("restore")

    def fail():
        raise RuntimeError("injected")

    class Fbo:
        def __init__(self, *_args):
            calls.append("construct")
            if failure == "construct":
                fail()
            self.bind = lambda: calls.append("bind") or (fail() if failure == "bind_raise" else failure != "bind")
            self.release = lambda: calls.append("release") or (fail() if failure == "release" else None)
            self.toImage = lambda: calls.append("readback") or (fail() if failure == "readback" else "image")

        def __del__(self):
            calls.append("destroy")

    def frame(*_args):
        calls.append("frame")
        if failure == "frame":
            fail()
        return failure != "empty"

    monkeypatch.setattr(QtOpenGL, "QOpenGLFramebufferObject", Fbo)
    monkeypatch.setitem(globals_, "offscreen_framebuffer_format", lambda: "format")
    monkeypatch.setitem(globals_, "_preserved_gl_render_state", preserved)
    host = Host(_document=object(), makeCurrent=lambda: calls.append("current"),
                doneCurrent=lambda: calls.append("done"), _render_puppet_frame=frame)
    if failure in {"construct", "bind_raise", "frame", "readback", "release"}:
        with pytest.raises(RuntimeError):
            host.render_offscreen_puppet(64, 32)
    else:
        assert host.render_offscreen_puppet(64, 32) == ("image" if failure is None else None)
    assert calls[:2] == ["current", "construct"]
    if failure == "construct":
        # Constructor traceback can hold the incomplete Python test double.
        assert "done" in calls
        return
    assert calls[-2:] == ["destroy", "done"]
    if failure in {"bind", "bind_raise"}:
        assert calls == ["current", "construct", "bind", "destroy", "done"]
    else:
        assert calls[-4:] == ["restore", "release", "destroy", "done"]


@pytest.mark.parametrize("document,width,height", [(None, 1, 1), (object(), 0, 1), (object(), 1, -1)])
def test_invalid_offscreen_target_never_acquires_context(document, width, height):
    host = Host(_document=document, makeCurrent=lambda: pytest.fail("context acquired"))
    assert host.render_offscreen_puppet(width, height) is None


def test_expression_physics_render_precedence(monkeypatch):
    expression = Expression("smile", [ExpressionParam("A", 4.0, "overwrite")])
    calls = []
    host = Host(
        _document=PuppetDocument(), _parameter_values={"A": 1.0},
        _active_expressions=[expression], _active_pose={}, _physics_outputs={},
        update=lambda: calls.append("update"),
    )
    host._physics = SimpleNamespace(step=lambda dt, values: calls.append(("physics", dt, values)) or {"A": 8.0})
    globals_ = PuppetCanvas._recompute_deformed_vertices.__globals__
    monkeypatch.setitem(globals_, "compose_all_drawables", lambda doc, values: calls.append(("render", values)) or {})
    host.step_physics(0.01, 2)
    assert calls == [("physics", 0.01, {"A": 4.0}), ("physics", 0.01, {"A": 4.0}),
                     ("render", {"A": 8.0}), "update"]
    assert host._parameter_values == {"A": 1.0}
    calls.clear()
    host.step_physics(0.01)
    assert calls == [("physics", 0.01, {"A": 4.0})]


def test_expression_and_pose_no_op_contracts():
    doc = PuppetDocument()
    doc.expressions = [Expression("smile", [])]
    doc.pose_groups = [PoseGroup("weapon", ["sword", "bow"])]
    host, calls = parameter_host()
    host._document = doc
    host._active_expressions = []
    host._active_pose = {}
    host.pose_changed = SimpleNamespace(emit=lambda *args: calls.append(args))
    assert host.add_expression("missing") is False
    assert host.add_expression("smile") is True
    assert host.add_expression("smile") is False
    assert host.remove_expression("missing") is False
    assert host.remove_expression("smile") is True
    assert calls == ["recompute", "update"] * 2
    calls.clear()
    assert host.set_pose_active("weapon", "missing") is False
    assert host.set_pose_active("weapon", "bow") is True
    assert host.set_pose_active("weapon", "bow") is True
    assert calls == ["recompute", "update", ("weapon", "bow")] * 2
    host.active_pose().clear()
    assert host._active_pose == {"weapon": "bow"}


def test_static_pose_visibility_and_clearing_document():
    doc = PuppetDocument()
    doc.drawables = [Drawable("sword", "", [], [], []), Drawable("bow", "", [], [], [])]
    doc.pose_groups = [PoseGroup("weapon", ["sword", "bow"])]
    host = Host(_document=doc, _parameter_values={}, _active_expressions=[],
                _active_pose={"weapon": "bow"}, _physics_outputs={})
    host._recompute_deformed_vertices()
    assert host._deformed_vertices == {}
    assert host.visibility() == {"sword": False, "bow": True}
    host.visibility().clear()
    assert host._visibility == {"sword": False, "bow": True}
    host._document = None
    host._recompute_deformed_vertices()
    assert host._deformed_vertices == host._visibility == host._part_opacity == {}
    assert host._drawable_opacity == host._drawable_tint == {}


def test_physics_timer_start_repeat_stop():
    calls = []
    timer = SimpleNamespace(active=False)

    def start():
        timer.active = True
        calls.append("start")

    def stop():
        timer.active = False
        calls.append("stop")

    timer.start, timer.stop, timer.isActive = start, stop, lambda: timer.active
    host = Host(_physics=SimpleNamespace(chain_ids=lambda: ["hair"]),
                _physics_timer=timer, _physics_clock=4.0, _physics_lag=1.0,
                isVisible=lambda: True)
    host._sync_physics_timer()
    assert host._physics_clock is None and host._physics_lag == 0.0
    host._physics_clock, host._physics_lag = 8.0, 0.01
    host._sync_physics_timer()
    assert host._physics_clock == 8.0 and host._physics_lag == 0.01
    host.isVisible = lambda: False
    host._sync_physics_timer()
    host._sync_physics_timer()
    assert calls == ["start", "stop"]


@pytest.mark.parametrize("panning,editing,target,expected", [
    (True, True, ("mesh", 0), "update"),
    (False, True, ("mesh", 0), "drag"),
    (False, True, None, "cursor"),
    (False, False, None, "cursor"),
])
def test_pointer_move_priority(panning, editing, target, expected):
    calls = []
    host = Host(_panning=panning, _mesh_edit_enabled=editing, _mesh_edit_target=target,
                _pan_anchor=(1.0, 2.0), _pan_x=0.0, _pan_y=0.0, _zoom=2.0,
                update=lambda: calls.append("update"),
                update_mesh_edit_drag=lambda *args: calls.append("drag"),
                cursor_moved=SimpleNamespace(emit=lambda *args: calls.append("cursor")))
    event = SimpleNamespace(position=lambda: SimpleNamespace(x=lambda: 3.0, y=lambda: 4.0))
    host.mouseMoveEvent(event)
    assert calls == [expected]
    if panning:
        assert (host._pan_x, host._pan_y, host._pan_anchor, host._user_view_locked) == (2.0, 2.0, (3.0, 4.0), True)


@pytest.mark.parametrize("moved", [False, True])
def test_mesh_drag_rebuilds_and_redraws_only_after_a_successful_move(monkeypatch, moved):
    host, calls = parameter_host()
    drawable = object()
    host._document = SimpleNamespace(drawable=lambda key: drawable)
    host._draw_list = ["old"]
    host._mesh_edit_enabled, host._mesh_edit_target = True, ("mesh", 2)
    globals_ = PuppetCanvas.update_mesh_edit_drag.__globals__
    monkeypatch.setitem(globals_, "move_vertex", lambda *args: calls.append(("move", args)) or moved)
    monkeypatch.setitem(globals_, "build_draw_list", lambda doc: calls.append("build") or ["new"])
    assert host.update_mesh_edit_drag(3.0, 4.0) is moved
    assert calls == [("move", (drawable, 2, 3.0, 4.0))] + (["build", "recompute", "update"] if moved else [])
    assert host._draw_list == (["new"] if moved else ["old"])


def test_parameter_conversion_runs_once_and_unknown_value_is_not_converted():
    host, calls = parameter_host()

    class Value:
        def __float__(self):
            calls.append("float")
            return 3.0

    host.force_parameter_values({"A": Value(), "unknown": Value()})
    assert calls == ["float", "recompute", "update"]


def test_recomposition_failure_keeps_values_and_does_not_schedule_update():
    host, calls = parameter_host()

    def fail():
        calls.append("recompute")
        raise RuntimeError("rig failed")

    host._recompute_deformed_vertices = fail
    with pytest.raises(RuntimeError, match="rig failed"):
        host.force_parameter_values({"A": 3.0})
    assert host._parameter_values == {"A": 3.0, "B": 2.0}
    assert calls == ["recompute"]
