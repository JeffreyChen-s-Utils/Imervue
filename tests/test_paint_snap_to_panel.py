"""The brush's Snap to panel keeps a stroke inside the comic panel it starts in.

Progress #49: the clipping was written (``BrushTool._panel_clipped_selection``,
``ToolDispatcher._panel_clip_for_point``) but never ran — Panel Cutter threw
its layout away, the workspace never passed ``panel_layout_provider``, and
nothing could turn ``snap_to_panel`` on. Panel Cutter now keeps the layout on
the document, the workspace hands it to the dispatcher (only while it fits
the canvas), and the brush strip has a **Snap to panel** box.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.document import PaintDocument
from Imervue.paint.manga_menu import commit_panel_layout
from Imervue.paint.manga_panels import layout_for_canvas, panel_grid
from Imervue.paint.tool_bar import PaintOptionsBar
from Imervue.paint.tool_dispatcher import DispatcherHooks, ToolDispatcher
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _two_panels():
    """A 100 × 60 page cut into two side-by-side panels with a 20 px gutter."""
    return panel_grid(width=100, height=60, rows=1, cols=2, gutter=20, border_width=2)


def test_panel_cutter_keeps_its_layout_on_the_document():
    doc = PaintDocument()
    doc.load_image(np.full((60, 100, 4), 255, np.uint8))
    workspace = SimpleNamespace(canvas=lambda: SimpleNamespace(document=lambda: doc,
                                                               update=lambda: None))
    assert commit_panel_layout(workspace, {"rows": 1, "cols": 2, "gutter": 20,
                                           "border": 2, "margin": 0}) is True
    assert doc.panel_layout is not None and len(doc.panel_layout.cells) == 2
    import copy
    assert copy.deepcopy(doc).panel_layout == doc.panel_layout


def test_a_layout_only_counts_on_a_canvas_of_its_size():
    layout = _two_panels()
    assert layout_for_canvas(layout, (60, 100, 4)) is layout
    assert layout_for_canvas(layout, (60, 120, 4)) is None
    assert layout_for_canvas(None, (60, 100, 4)) is None


def _stroke(snap: bool, layout) -> np.ndarray:
    state = ts.load_tool_state()
    state.set_tool("brush")
    state.set_foreground((200, 0, 0))
    state.set_brush(size=12, hardness=1.0, opacity=1.0)
    state.set_snap_to_panel(snap)
    canvas = np.zeros((60, 100, 4), np.uint8)
    dispatcher = ToolDispatcher(state, image_provider=lambda: canvas,
                                hooks=DispatcherHooks(panel_layout_provider=lambda: layout))
    for phase, x in (("press", 20.0), ("move", 50.0), ("move", 80.0), ("release", 80.0)):
        dispatcher(PointerEvent(phase=phase, x=x, y=30.0, button=1, modifiers=0, pressure=1.0))
    return canvas


def test_with_snap_on_a_stroke_stays_in_its_starting_panel():
    layout = _two_panels()
    first, second = layout.cells
    canvas = _stroke(True, layout)
    ys, xs = np.nonzero(canvas[..., 3])
    assert len(xs) and xs.max() < first.x + first.w
    assert not canvas[:, second.x:, 3].any()


def test_with_snap_off_the_stroke_crosses_the_gutter():
    canvas = _stroke(False, _two_panels())
    assert canvas[:, 75:85, 3].any()


def test_without_a_layout_snap_changes_nothing():
    assert np.array_equal(_stroke(True, None), _stroke(False, None))


def test_the_brush_strip_toggles_and_shows_the_setting(qapp):
    state = ts.load_tool_state()
    bar = PaintOptionsBar(state)
    try:
        bar._snap_to_panel.setChecked(True)  # noqa: SLF001
        assert state.snap_to_panel is True
        assert ts.ToolState.from_dict(state.to_dict()).snap_to_panel is True
        assert state.set_snap_to_panel(True) is False                    # no change, no event
        state.set_snap_to_panel(False)
        assert not bar._snap_to_panel.isChecked()  # noqa: SLF001
    finally:
        bar.deleteLater()


def test_the_workspace_passes_the_documents_layout_while_it_fits():
    from Imervue.paint.paint_workspace import PaintWorkspace
    doc = PaintDocument()
    doc.load_image(np.zeros((60, 100, 4), np.uint8))
    host = SimpleNamespace(_canvas=SimpleNamespace(document=lambda: doc))
    assert PaintWorkspace._panel_layout(host) is None
    doc.panel_layout = _two_panels()
    assert PaintWorkspace._panel_layout(host) is doc.panel_layout
    doc.load_image(np.zeros((80, 100, 4), np.uint8))            # a different page size
    assert PaintWorkspace._panel_layout(host) is None
