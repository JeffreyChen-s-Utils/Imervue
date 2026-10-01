"""The Pen's Smooth option runs one curve through the clicked points.

``paint/catmull_rom_spline.py`` (a Catmull-Rom curve through a polyline's
points) had no caller; the pen joined clicked anchors with straight lines unless
the user dragged out handles. With **Smooth** ticked on the Pen's Options bar
strip, the preview and the committed stroke follow the curve instead. These
tests drive the pure path helpers and the tool on stand-ins, so they run on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.bezier_path import BezierPath, PathNode
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.pen_commit import (
    SMOOTH_SAMPLES_PER_SEGMENT,
    commit_pen_path,
    smooth_points,
    smoothed_path,
)
from Imervue.paint.tool_bar import PaintOptionsBar
from Imervue.paint.tools.special import _BezierPenTool
from Imervue.user_settings.user_setting_dict import user_setting_dict

_ZIGZAG = [(10.0, 50.0), (40.0, 10.0), (70.0, 50.0), (100.0, 10.0)]


@pytest.fixture(autouse=True)
def _clean():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _path(points, closed: bool = False) -> BezierPath:
    return BezierPath(nodes=[PathNode(anchor=p) for p in points], closed=closed)


def test_the_curve_passes_through_every_clicked_point():
    points = smooth_points(_path(_ZIGZAG))
    assert len(points) == (len(_ZIGZAG) - 1) * SMOOTH_SAMPLES_PER_SEGMENT + 1
    for anchor in _ZIGZAG:
        assert min(np.hypot(x - anchor[0], y - anchor[1]) for x, y in points) < 1e-6


def test_the_curve_bends_between_the_points():
    """Halfway from (10, 50) to (40, 10) a straight line sits at (25, 30); the curve does not."""
    x, y = smooth_points(_path(_ZIGZAG))[SMOOTH_SAMPLES_PER_SEGMENT // 2]
    assert np.hypot(x - 25.0, y - 30.0) > 1.0


def test_a_closed_path_wraps_round():
    points = smooth_points(_path(_ZIGZAG[:3], closed=True))
    assert len(points) == 3 * SMOOTH_SAMPLES_PER_SEGMENT
    smoothed = smoothed_path(_path(_ZIGZAG[:3], closed=True))
    assert smoothed.closed is True
    assert all(node.handle_in is None and node.handle_out is None for node in smoothed.nodes)


def _workspace(path: BezierPath, *, smooth: bool):
    state = ts.load_tool_state()
    state.set_foreground((200, 0, 0))
    state.set_brush(size=3, opacity=1.0, hardness=1.0)
    state.set_pen_smooth(smooth)
    image = np.zeros((70, 120, 4), np.uint8)
    layer = SimpleNamespace(image=image, vector_data=None)
    document = SimpleNamespace(active_layer=lambda: layer, invalidate_composite=lambda: None)
    workspace = SimpleNamespace(_bezier_pen_path=path, state=lambda: state,
                                canvas=lambda: SimpleNamespace(document=lambda: document))
    return workspace, image


@pytest.mark.parametrize("smooth", [False, True])
def test_committing_paints_lines_or_the_curve(smooth):
    workspace, image = _workspace(_path(_ZIGZAG), smooth=smooth)
    assert commit_pen_path(workspace) is True
    on_the_straight_line = bool(image[30, 25, 3] == 255)    # the straight segment's midpoint
    assert on_the_straight_line is (not smooth)
    assert image[50, 10, 3] == 255 and image[10, 100, 3] == 255   # both ends either way
    assert workspace._bezier_pen_path.nodes == []


def test_the_preview_follows_the_setting():
    state = ts.load_tool_state()
    shown = []
    tool = _BezierPenTool(state, shown.append)
    tool.attach_workspace(SimpleNamespace())
    for x, y in _ZIGZAG[:3]:
        tool.handle(PointerEvent(phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0), None)
        tool.handle(PointerEvent(phase="release", x=x, y=y, button=1, modifiers=0, pressure=1.0), None)
    assert len(shown[-1]["points"]) == 3
    state.set_pen_smooth(True)
    tool.handle(PointerEvent(phase="press", x=100, y=10, button=1, modifiers=0, pressure=1.0), None)
    assert len(shown[-1]["points"]) == 3 * SMOOTH_SAMPLES_PER_SEGMENT + 1


def test_the_setting_is_remembered_and_shown_on_the_pen_strip(qapp):
    state = ts.load_tool_state()
    bar = PaintOptionsBar(state)
    try:
        bar.set_tool("bezier_pen")
        assert bar._stack.currentWidget().isAncestorOf(bar._pen_smooth)
        bar._pen_smooth.setChecked(True)
        assert state.pen_smooth is True
        assert ts.ToolState.from_dict(state.to_dict()).pen_smooth is True
        state.set_pen_smooth(False)
        assert not bar._pen_smooth.isChecked()
    finally:
        bar.deleteLater()
