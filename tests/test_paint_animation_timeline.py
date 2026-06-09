"""Tests for the animation-timeline model + dock + workspace wiring."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.animation_dock import AnimationDock
from Imervue.paint.animation_timeline import (
    DEFAULT_FPS,
    FPS_MAX,
    FPS_MIN,
    MAX_FRAMES,
    AnimationTimeline,
    Frame,
    from_canvas_snapshots,
    thumbnail_for,
)
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _rgba(h: int = 16, w: int = 16, c: tuple[int, int, int] = (10, 20, 30)):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = c[0]
    arr[..., 1] = c[1]
    arr[..., 2] = c[2]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Frame validation
# ---------------------------------------------------------------------------


def test_frame_accepts_valid_rgba():
    arr = _rgba()
    frame = Frame(image=arr)
    assert frame.image is arr


def test_frame_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        Frame(image=bad)


def test_frame_rejects_wrong_dtype():
    bad = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        Frame(image=bad)


# ---------------------------------------------------------------------------
# Timeline mutation
# ---------------------------------------------------------------------------


def test_empty_timeline_has_zero_frames():
    t = AnimationTimeline()
    assert len(t) == 0
    assert t.current_index == 0
    assert t.current_frame() is None


def test_add_frame_returns_index_and_advances_pointer():
    t = AnimationTimeline()
    i = t.add_frame(_rgba())
    assert i == 0
    assert t.current_index == 0
    j = t.add_frame(_rgba())
    assert j == 1
    assert t.current_index == 1


def test_add_frame_copies_input_so_caller_can_mutate():
    t = AnimationTimeline()
    arr = _rgba()
    t.add_frame(arr)
    arr[0, 0, 0] = 200
    assert int(t.frames[0].image[0, 0, 0]) != 200


def test_add_frame_caps_at_max_frames():
    t = AnimationTimeline()
    # Append the max — last add succeeds, next must raise.
    arr = _rgba(2, 2)
    for _ in range(MAX_FRAMES):
        t.add_frame(arr)
    with pytest.raises(ValueError):
        t.add_frame(arr)


def test_insert_frame_clamps_index():
    t = from_canvas_snapshots([_rgba() for _ in range(3)])
    i = t.insert_frame(_rgba(), 99)
    assert i == 3   # appended at end
    assert len(t) == 4


def test_remove_frame_drops_entry_and_clamps_pointer():
    t = from_canvas_snapshots([_rgba() for _ in range(3)])
    t.set_current_index(2)
    assert t.remove_frame(2) is True
    assert len(t) == 2
    assert t.current_index == 1   # clamped down


def test_remove_last_frame_refused():
    t = from_canvas_snapshots([_rgba()])
    assert t.remove_frame(0) is False
    assert len(t) == 1


def test_remove_out_of_range_returns_false():
    t = from_canvas_snapshots([_rgba(), _rgba()])
    assert t.remove_frame(99) is False


def test_replace_frame_overwrites_image():
    t = from_canvas_snapshots([_rgba(c=(10, 20, 30))])
    new = _rgba(c=(99, 99, 99))
    assert t.replace_frame(new, 0) is True
    assert int(t.frames[0].image[0, 0, 0]) == 99


# ---------------------------------------------------------------------------
# Pointer / playhead
# ---------------------------------------------------------------------------


def test_set_current_index_validates_range():
    t = from_canvas_snapshots([_rgba(), _rgba()])
    assert t.set_current_index(99) is False
    assert t.set_current_index(0) is False  # already at 0
    assert t.set_current_index(1) is True
    assert t.current_index == 1


def test_advance_with_loop_wraps_to_zero():
    t = from_canvas_snapshots([_rgba(), _rgba()])
    t.set_current_index(1)
    nxt = t.advance(loop=True)
    assert nxt == 0


def test_advance_without_loop_clamps_at_last():
    t = from_canvas_snapshots([_rgba(), _rgba()])
    t.set_current_index(1)
    nxt = t.advance(loop=False)
    assert nxt == 1


def test_advance_on_empty_timeline_returns_zero():
    t = AnimationTimeline()
    assert t.advance() == 0


# ---------------------------------------------------------------------------
# previous_frame for onion-skin
# ---------------------------------------------------------------------------


def test_previous_frame_returns_prior_image_at_index_one():
    t = from_canvas_snapshots([_rgba(c=(11, 22, 33)), _rgba(c=(99, 99, 99))])
    t.set_current_index(1)
    prev = t.previous_frame()
    assert prev is not None
    assert int(prev.image[0, 0, 0]) == 11


def test_previous_frame_at_index_zero_is_none():
    t = from_canvas_snapshots([_rgba(), _rgba()])
    t.set_current_index(0)
    assert t.previous_frame() is None


def test_previous_frame_with_single_frame_is_none():
    t = from_canvas_snapshots([_rgba()])
    assert t.previous_frame() is None


# ---------------------------------------------------------------------------
# FPS clamping
# ---------------------------------------------------------------------------


def test_set_fps_clamps_to_min_max():
    t = AnimationTimeline()
    assert t.set_fps(0) == FPS_MIN
    assert t.set_fps(1000) == FPS_MAX
    assert t.set_fps(24) == 24


def test_default_fps_within_range():
    assert FPS_MIN <= DEFAULT_FPS <= FPS_MAX


# ---------------------------------------------------------------------------
# thumbnail_for
# ---------------------------------------------------------------------------


def test_thumbnail_returns_at_most_requested_size():
    f = Frame(image=_rgba(120, 200))
    out = thumbnail_for(f, size=64)
    assert out.shape[0] <= 64
    assert out.shape[1] <= 64


def test_thumbnail_passes_small_image_through():
    f = Frame(image=_rgba(8, 8))
    out = thumbnail_for(f, size=64)
    assert out.shape == (8, 8, 4)


def test_thumbnail_rejects_zero_size():
    f = Frame(image=_rgba(8, 8))
    with pytest.raises(ValueError):
        thumbnail_for(f, size=0)


# ---------------------------------------------------------------------------
# Dock UI smoke tests
# ---------------------------------------------------------------------------


def test_dock_starts_empty(qapp):
    dock = AnimationDock()
    try:
        assert len(dock.timeline()) == 0
        assert dock.is_playing() is False
    finally:
        dock.deleteLater()


def test_dock_set_timeline_swaps_model(qapp):
    dock = AnimationDock()
    try:
        new = from_canvas_snapshots([_rgba(), _rgba()])
        dock.set_timeline(new)
        assert dock.timeline() is new
    finally:
        dock.deleteLater()


def test_dock_play_requires_at_least_two_frames(qapp):
    dock = AnimationDock()
    try:
        # Single frame — start_playback should be a no-op.
        dock.timeline().add_frame(_rgba())
        dock.start_playback()
        assert dock.is_playing() is False
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# Workspace integration
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_workspace_attaches_animation_dock(workspace):
    assert isinstance(workspace._animation_dock, AnimationDock)  # noqa: SLF001


def test_add_frame_button_snapshots_canvas(workspace):
    workspace._on_animation_add_frame()  # noqa: SLF001
    timeline = workspace._animation_dock.timeline()  # noqa: SLF001
    assert len(timeline) == 1


def test_remove_frame_button_drops_entry(workspace):
    workspace._on_animation_add_frame()  # noqa: SLF001
    workspace._on_animation_add_frame()  # noqa: SLF001
    assert len(workspace._animation_dock.timeline()) == 2  # noqa: SLF001
    workspace._on_animation_remove_frame(1)  # noqa: SLF001
    assert len(workspace._animation_dock.timeline()) == 1  # noqa: SLF001


def test_frame_select_pastes_image_into_layer(workspace):
    canvas = workspace.canvas()
    document = canvas.document()
    layer = document.active_layer()
    layer.image[..., :3] = (10, 20, 30)
    workspace._on_animation_add_frame()  # noqa: SLF001
    layer.image[..., :3] = (90, 90, 90)
    workspace._on_animation_add_frame()  # noqa: SLF001
    # Now select the first frame again — layer image must revert.
    workspace._on_animation_frame_selected(0)  # noqa: SLF001
    assert int(layer.image[0, 0, 0]) == 10


def test_onion_skin_source_set_after_second_frame(workspace):
    workspace._on_animation_add_frame()  # noqa: SLF001
    workspace._on_animation_add_frame()  # noqa: SLF001
    canvas = workspace.canvas()
    # The onion-skin source callable returns the previous frame buffer.
    source = canvas._onion_skin_source  # noqa: SLF001
    assert source is not None
    buf = source()
    assert buf is not None
    assert buf.shape[2] == 4
