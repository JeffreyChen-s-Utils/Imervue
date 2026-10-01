"""The Lasso's Magnetic option snaps a drawn outline onto the nearby edge.

``paint/magnetic_lasso.py`` held the edge-snap maths but no tool used it. The
Options bar now shows **Magnetic** for the Lasso; with it on, the outline's
points move to the strongest edge of the layer within 10 px on release.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.tool_bar import PaintOptionsBar
from Imervue.paint.tools.select import LassoSelectTool, _SelectionContext
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _canvas() -> np.ndarray:
    """Black on the left, white from column 30 on: one strong vertical edge."""
    canvas = np.zeros((60, 60, 4), np.uint8)
    canvas[..., 3] = 255
    canvas[:, 30:, :3] = 255
    return canvas


def _lasso(magnetic: bool) -> np.ndarray:
    state = ts.load_tool_state()
    state.set_lasso_magnetic(magnetic)
    written = []
    tool = LassoSelectTool(_SelectionContext(state, lambda: None, written.append))
    canvas = _canvas()
    # A rectangle whose right side is drawn at x = 24, six pixels short of the edge.
    path = [(5, 10), (24, 10), (24, 50), (5, 50)]
    tool.handle(PointerEvent(phase="press", x=5, y=10, button=1, modifiers=0, pressure=1.0), canvas)
    for x, y in path[1:]:
        tool.handle(PointerEvent(phase="move", x=x, y=y, button=1, modifiers=0, pressure=1.0), canvas)
    tool.handle(PointerEvent(phase="release", x=5, y=10, button=1, modifiers=0, pressure=1.0), canvas)
    (mask,) = written
    return mask


def _right_edge(mask: np.ndarray) -> int:
    return int(np.nonzero(mask[30])[0].max())


def test_without_magnetic_the_outline_stays_where_it_was_drawn():
    assert _right_edge(_lasso(False)) == 24


def test_magnetic_pulls_the_outline_onto_the_edge():
    assert _right_edge(_lasso(True)) in (29, 30)


def test_the_setting_is_remembered_and_announced():
    state = ts.load_tool_state()
    events = []
    state.subscribe(events.append)
    assert state.set_lasso_magnetic(True) is True
    assert state.set_lasso_magnetic(True) is False
    assert events == [ts.EVENT_SELECTION_MODE]
    assert ts.ToolState.from_dict(state.to_dict()).lasso_magnetic is True
    assert ts.ToolState.from_dict({}).lasso_magnetic is False


def test_the_options_bar_shows_magnetic_for_the_lasso_only(qapp):
    state = ts.load_tool_state()
    bar = PaintOptionsBar(state)
    try:
        box = bar._lasso_magnetic
        bar.set_tool("select_lasso")
        assert not box.isHidden()
        box.setChecked(True)
        assert state.lasso_magnetic is True
        bar.set_tool("select_rect")
        assert box.isHidden()
        state.set_lasso_magnetic(False)
        assert not box.isChecked()
    finally:
        bar.deleteLater()
