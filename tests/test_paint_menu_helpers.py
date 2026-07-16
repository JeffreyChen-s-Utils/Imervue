"""Small paint menu-helper regressions (GP12 / GP14 / GP20).

Each is a localized correctness / crash fix exercised on a fake workspace or a
pure function -- no Qt widget is constructed, so this runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.paint.edit_menu import commit_stroke_selection
from Imervue.paint.file_menu import _FileMenuBridge
from Imervue.paint.transform_handles import MIN_BOX_SIZE, from_rect


# ---------------------------------------------------------------------------
# GP12 -- page export read the wrong workspace attribute and always no-opped.
# ---------------------------------------------------------------------------


def test_current_project_reads_paint_project():
    project = object()
    ws = SimpleNamespace(_paint_project=project)
    bridge = SimpleNamespace(_workspace=ws)
    assert _FileMenuBridge._current_project(bridge) is project


def test_current_project_none_when_no_project():
    bridge = SimpleNamespace(_workspace=SimpleNamespace())
    assert _FileMenuBridge._current_project(bridge) is None


# ---------------------------------------------------------------------------
# GP14 -- stroking a selection with a transparent foreground crashed.
# ---------------------------------------------------------------------------


def _stroke_workspace(foreground):
    doc = SimpleNamespace(
        active_layer=lambda: SimpleNamespace(image=np.zeros((4, 4, 4), np.uint8)),
        selection=lambda: np.ones((4, 4), dtype=bool),
    )
    return SimpleNamespace(
        canvas=lambda: SimpleNamespace(document=lambda: doc),
        state=lambda: SimpleNamespace(foreground=foreground),
    )


def test_stroke_selection_transparent_foreground_returns_false():
    # foreground is None when the swatch is transparent -> no colour to stroke.
    assert commit_stroke_selection(_stroke_workspace(None), {}) is False


# ---------------------------------------------------------------------------
# GP20 -- from_rect raised on a sub-4px marquee.
# ---------------------------------------------------------------------------


def test_from_rect_clamps_tiny_selection():
    box = from_rect(10, 10, 1, 1)   # 1px marquee would raise before the clamp
    assert box.width >= MIN_BOX_SIZE
    assert box.height >= MIN_BOX_SIZE
    assert box.cx == 10.5           # still centred on the marquee
    assert box.cy == 10.5


def test_from_rect_preserves_a_large_selection():
    box = from_rect(0, 0, 100, 50)
    assert box.width == 100.0
    assert box.height == 50.0
