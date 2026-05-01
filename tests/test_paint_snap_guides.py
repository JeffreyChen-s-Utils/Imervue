"""Tests for snap-to-edge candidates + snap_point + crop integration."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.snap_guides import (
    DEFAULT_SNAP_THRESHOLD_PX,
    SNAP_HORIZONTAL,
    SNAP_VERTICAL,
    collect_canvas_candidates,
    collect_layer_candidates,
    snap_point,
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
# collect_canvas_candidates
# ---------------------------------------------------------------------------


def test_canvas_candidates_include_edges_and_center():
    xs, ys = collect_canvas_candidates((100, 200))
    assert 0.0 in xs and 200.0 in xs
    assert 100.0 in xs   # centre x
    assert 0.0 in ys and 100.0 in ys
    assert 50.0 in ys   # centre y


def test_canvas_candidates_rejects_zero_dim():
    with pytest.raises(ValueError):
        collect_canvas_candidates((0, 100))


# ---------------------------------------------------------------------------
# collect_layer_candidates
# ---------------------------------------------------------------------------


def _layer_with_disk(h: int, w: int, top: int, left: int,
                     ih: int, iw: int) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[top:top + ih, left:left + iw, :3] = (200, 100, 50)
    arr[top:top + ih, left:left + iw, 3] = 255
    return arr


def test_layer_candidates_emit_bbox_edges():
    layer = _layer_with_disk(40, 40, top=10, left=8, ih=12, iw=20)
    xs, ys = collect_layer_candidates([layer])
    # Left/right edges of the disk.
    assert 8.0 in xs
    assert 28.0 in xs
    # Top/bottom edges.
    assert 10.0 in ys
    assert 22.0 in ys


def test_layer_candidates_skip_fully_transparent_layer():
    transparent = np.zeros((20, 20, 4), dtype=np.uint8)
    xs, ys = collect_layer_candidates([transparent])
    assert xs == []
    assert ys == []


def test_layer_candidates_skip_non_rgba_input():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    xs, ys = collect_layer_candidates([bad])
    assert xs == [] and ys == []


def test_layer_candidates_aggregate_multiple_layers():
    a = _layer_with_disk(40, 40, top=2, left=2, ih=4, iw=4)
    b = _layer_with_disk(40, 40, top=20, left=20, ih=4, iw=4)
    xs, ys = collect_layer_candidates([a, b])
    assert {2.0, 6.0, 20.0, 24.0}.issubset(set(xs))
    assert {2.0, 6.0, 20.0, 24.0}.issubset(set(ys))


# ---------------------------------------------------------------------------
# snap_point
# ---------------------------------------------------------------------------


def test_snap_pulls_to_nearest_within_threshold():
    sx, sy, hits = snap_point(
        102.0, 50.5,
        x_candidates=[0, 100, 200],
        y_candidates=[0, 50, 100],
        threshold=5,
    )
    assert sx == 100.0
    assert sy == 50.0
    # Both axes hit a candidate.
    axes = [a for a, _v in hits]
    assert SNAP_VERTICAL in axes
    assert SNAP_HORIZONTAL in axes


def test_snap_passes_through_when_no_candidate_close():
    sx, sy, hits = snap_point(
        500.0, 500.0,
        x_candidates=[0, 100],
        y_candidates=[0, 100],
        threshold=4,
    )
    assert sx == 500.0
    assert sy == 500.0
    assert hits == []


def test_snap_zero_threshold_disables_snapping():
    sx, sy, hits = snap_point(
        99.0, 99.0,
        x_candidates=[100], y_candidates=[100],
        threshold=0,
    )
    assert (sx, sy) == (99.0, 99.0)
    assert hits == []


def test_snap_empty_candidates_passes_through():
    sx, sy, hits = snap_point(50.0, 50.0)
    assert (sx, sy) == (50.0, 50.0)
    assert hits == []


def test_snap_default_threshold_is_documented():
    assert DEFAULT_SNAP_THRESHOLD_PX > 0


# ---------------------------------------------------------------------------
# Crop tool integration via _maybe_snap_to_edges
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def _press(x, y):
    return PointerEvent(
        phase="press", x=x, y=y, button=1, modifiers=0, pressure=1.0,
    )


def _release(x, y):
    return PointerEvent(
        phase="release", x=x, y=y, button=0, modifiers=0, pressure=1.0,
    )


def test_crop_release_unaffected_when_snap_disabled(workspace):
    workspace.state().snap_to_edges = False
    document = workspace.canvas().document()
    h, w = document.shape
    crop_tool = workspace._dispatcher._handlers["crop"]   # noqa: SLF001
    crop_tool.handle(_press(2, 2), workspace.canvas().current_image())
    crop_tool.handle(_release(w - 3, h - 3), workspace.canvas().current_image())
    h_after, w_after = workspace.canvas().document().shape
    # Crop went through with the unsnapped corners (≈ canvas minus
    # a 2-3 pixel border).
    assert (h_after, w_after) == (h - 5, w - 5)


def test_crop_release_snaps_to_canvas_edge_when_enabled(workspace):
    workspace.state().snap_to_edges = True
    document = workspace.canvas().document()
    h, w = document.shape
    crop_tool = workspace._dispatcher._handlers["crop"]   # noqa: SLF001
    crop_tool.handle(_press(0, 0), workspace.canvas().current_image())
    # Release just inside the canvas edge — snap should pull it onto
    # the edge so the resulting crop covers the full canvas.
    crop_tool.handle(_release(w - 2, h - 2), workspace.canvas().current_image())
    assert workspace.canvas().document().shape == (h, w)


def test_snap_helper_no_workspace_returns_input(qapp):
    """When the crop tool isn't attached to a workspace, the snap
    helper must short-circuit rather than crash."""
    state = ts.load_tool_state()
    state.snap_to_edges = True
    from Imervue.paint.tool_dispatcher import _CropTool
    tool = _CropTool(state)
    out = tool._maybe_snap_to_edges(50.0, 50.0, (100, 100))   # noqa: SLF001
    assert out == (50.0, 50.0)


# ---------------------------------------------------------------------------
# Persistence — snap_to_edges round-trips
# ---------------------------------------------------------------------------


def test_snap_to_edges_persists_via_to_dict():
    state = ts.load_tool_state()
    state.snap_to_edges = True
    raw = state.to_dict()
    assert raw["snap_to_edges"] is True


def test_snap_to_edges_default_false():
    state = ts.load_tool_state()
    assert state.snap_to_edges is False
