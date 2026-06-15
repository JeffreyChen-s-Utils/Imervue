"""Tests for pen-path commit-to-active-layer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.bezier_path import BezierPath, PathNode
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.pen_commit import _options_from_state, commit_pen_path
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# commit_pen_path — happy path + guards
# ---------------------------------------------------------------------------


def test_commit_returns_false_when_path_missing(qapp):
    """Workspace with no _bezier_pen_path attribute → no-op False."""
    ws = PaintWorkspace()
    try:
        # Force-remove the attribute so we exercise the missing path.
        if hasattr(ws, "_bezier_pen_path"):
            delattr(ws, "_bezier_pen_path")
        assert commit_pen_path(ws) is False
    finally:
        ws.deleteLater()


def test_commit_returns_false_for_single_anchor(qapp):
    ws = PaintWorkspace()
    try:
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[PathNode(anchor=(10.0, 10.0))],
        )
        assert commit_pen_path(ws) is False
    finally:
        ws.deleteLater()


def test_commit_returns_true_for_two_anchors_and_paints(qapp):
    """Two anchors → at least one segment → ``stroke_along_path``
    fires and the active layer's pixels change."""
    ws = PaintWorkspace()
    try:
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 30.0)),
                PathNode(anchor=(50.0, 30.0)),
            ],
        )
        ws.state().set_brush(size=8)
        ws.state().set_foreground((255, 0, 0))
        layer = ws.canvas().document().active_layer()
        before = layer.image.copy()
        assert commit_pen_path(ws) is True
        assert (layer.image != before).any()
    finally:
        ws.deleteLater()


def test_commit_clears_path_on_success(qapp):
    ws = PaintWorkspace()
    try:
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 30.0)),
                PathNode(anchor=(50.0, 30.0)),
            ],
        )
        commit_pen_path(ws)
        assert ws._bezier_pen_path.nodes == []  # noqa: SLF001
        assert ws._bezier_pen_path.closed is False  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_commit_invalidates_composite(qapp):
    ws = PaintWorkspace()
    try:
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 30.0)),
                PathNode(anchor=(50.0, 30.0)),
            ],
        )
        # Prime the composite cache so we can verify it's dropped.
        document = ws.canvas().document()
        document.composite()
        assert document._composite_cache is not None  # noqa: SLF001
        commit_pen_path(ws)
        assert document._composite_cache is None  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# _BezierPenTool.cancel — auto-commit on tool switch
#
# Without this, switching tools mid-pen-session left the path attached to
# the workspace; the layer never received the rasterised stroke so users
# saw the drawing "disappear" until they clicked another anchor (which
# revived the overlay because ``_refresh_overlay`` reads the saved path).
# ---------------------------------------------------------------------------


def test_cancel_auto_commits_path_with_two_or_more_anchors(qapp):
    from Imervue.paint.tool_dispatcher import _BezierPenTool

    ws = PaintWorkspace()
    try:
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 30.0)),
                PathNode(anchor=(50.0, 30.0)),
            ],
        )
        ws.state().set_brush(size=8)
        ws.state().set_foreground((255, 0, 0))
        layer = ws.canvas().document().active_layer()
        before = layer.image.copy()

        tool = _BezierPenTool(ws.state())
        tool.attach_workspace(ws)
        tool.cancel()

        assert (layer.image != before).any()
        assert ws._bezier_pen_path.nodes == []  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_cancel_discards_lone_anchor_without_painting(qapp):
    from Imervue.paint.tool_dispatcher import _BezierPenTool

    ws = PaintWorkspace()
    try:
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[PathNode(anchor=(10.0, 30.0))],
        )
        ws.state().set_brush(size=8)
        ws.state().set_foreground((255, 0, 0))
        layer = ws.canvas().document().active_layer()
        before = layer.image.copy()

        tool = _BezierPenTool(ws.state())
        tool.attach_workspace(ws)
        tool.cancel()

        # No segment to rasterise, but the lingering anchor must be
        # cleared so the next pen session starts clean.
        assert (layer.image == before).all()
        assert ws._bezier_pen_path.nodes == []  # noqa: SLF001
        assert ws._bezier_pen_path.closed is False  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_cancel_clears_overlay(qapp):
    from Imervue.paint.tool_dispatcher import _BezierPenTool

    ws = PaintWorkspace()
    try:
        captured: list = []
        tool = _BezierPenTool(ws.state(), overlay_setter=captured.append)
        tool.attach_workspace(ws)
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 30.0)),
                PathNode(anchor=(50.0, 30.0)),
            ],
        )
        tool.cancel()
        assert captured[-1] is None
    finally:
        ws.deleteLater()


def test_cancel_without_workspace_is_safe(qapp):
    """When the dispatcher constructs the pen tool but the workspace
    hasn't called ``attach_workspace`` yet (early-init paths in tests),
    ``cancel`` must not raise — it just clears its own state."""
    from Imervue.paint.tool_dispatcher import _BezierPenTool
    from Imervue.paint import tool_state as ts

    state = ts.load_tool_state()
    tool = _BezierPenTool(state)
    tool.cancel()  # must not raise


# ---------------------------------------------------------------------------
# _options_from_state
# ---------------------------------------------------------------------------


def test_options_from_state_carries_brush_size():
    state = ts.load_tool_state()
    state.set_brush(size=42, opacity=0.7, hardness=0.4, blend_mode="multiply")
    state.set_foreground((10, 20, 30))
    options = _options_from_state(state)
    assert options.size == 42
    assert options.opacity == pytest.approx(0.7)
    assert options.hardness == pytest.approx(0.4)
    assert options.blend_mode == "multiply"
    assert options.color == (10, 20, 30)


def test_options_from_state_default_brush_round_trips():
    state = ts.load_tool_state()
    options = _options_from_state(state)
    # Defaults must produce a usable BrushStrokeOptions (size > 0,
    # opacity > 0) so a pen-tool first-time user gets visible output.
    assert options.size > 0
    assert options.opacity > 0


# Keep numpy import live to support future helpers.
_USED_NP = np.array
