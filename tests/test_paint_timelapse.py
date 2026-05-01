"""Tests for the time-lapse export pipeline."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.action_recorder import Action, ActionRecording
from Imervue.paint.document import PaintDocument
from Imervue.paint.timelapse import (
    MAX_TIMELAPSE_FRAMES,
    frames_to_animation,
    render_timelapse_frames,
)


def _doc(h: int = 8, w: int = 8) -> PaintDocument:
    document = PaintDocument()
    document.load_image(np.zeros((h, w, 4), dtype=np.uint8))
    return document


def _paint_target(document: PaintDocument):
    """Return a target callable that paints a row of the active layer.

    Each ``(kind, params)`` carries a ``row`` index and a ``color``
    triplet — the target writes that row to the active layer's image
    so each replayed action visibly mutates the document's composite.
    """
    def target(kind: str, params: dict) -> None:
        if kind != "paint_row":
            return
        row = int(params.get("row", 0))
        color = tuple(int(c) for c in params.get("color", (0, 0, 0)))
        layer = document.active_layer()
        layer.image[row, :, :3] = color
        layer.image[row, :, 3] = 255
        document.invalidate_composite()
    return target


def _recording_with_rows(rows: list[tuple[int, tuple[int, int, int]]]) -> ActionRecording:
    return ActionRecording(
        name="r",
        actions=[
            Action(kind="paint_row", params={"row": r, "color": list(c)})
            for r, c in rows
        ],
    )


# ---------------------------------------------------------------------------
# render_timelapse_frames
# ---------------------------------------------------------------------------


def test_replays_every_action_and_captures_frames():
    document = _doc()
    rec = _recording_with_rows([(0, (255, 0, 0)), (1, (0, 255, 0)), (2, (0, 0, 255))])
    frames = render_timelapse_frames(rec, _paint_target(document), document)
    # Initial composite + 3 post-action snapshots = 4 frames.
    assert len(frames) == 4


def test_omitting_initial_frame():
    document = _doc()
    rec = _recording_with_rows([(0, (255, 0, 0)), (1, (0, 255, 0))])
    frames = render_timelapse_frames(
        rec, _paint_target(document), document, include_initial=False,
    )
    assert len(frames) == 2


def test_frame_every_subsamples_recordings():
    document = _doc()
    rec = _recording_with_rows([(i, (i * 30, 0, 0)) for i in range(8)])
    frames = render_timelapse_frames(
        rec, _paint_target(document), document,
        frame_every=4, include_initial=False,
    )
    # Snapshots at action indices 4 and 8 → 2 frames (1-based).
    assert len(frames) == 2


def test_frames_grow_with_replayed_actions():
    """Each captured frame reflects the document state AT that step,
    not the final state — so consecutive frames differ in the row
    most-recently painted."""
    document = _doc()
    rec = _recording_with_rows([(0, (200, 0, 0)), (4, (0, 200, 0))])
    frames = render_timelapse_frames(
        rec, _paint_target(document), document, include_initial=False,
    )
    assert len(frames) == 2
    assert frames[0][0, 0, 0] == 200   # first row painted red after step 1
    assert frames[1][4, 0, 1] == 200   # row 4 painted green after step 2


def test_rejects_zero_frame_every():
    document = _doc()
    rec = _recording_with_rows([(0, (200, 0, 0))])
    with pytest.raises(ValueError):
        render_timelapse_frames(
            rec, _paint_target(document), document, frame_every=0,
        )


def test_target_exceptions_propagate():
    document = _doc()
    rec = _recording_with_rows([(0, (200, 0, 0))])

    def boom(_kind: str, _params: dict) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        render_timelapse_frames(rec, boom, document)


def test_caps_at_max_frame_budget():
    """A pathological recording must not allocate unlimited memory."""
    document = _doc(h=4, w=4)
    rec = _recording_with_rows([(0, (200, 0, 0))] * (MAX_TIMELAPSE_FRAMES + 100))
    frames = render_timelapse_frames(
        rec, _paint_target(document), document,
        include_initial=False,
    )
    assert len(frames) <= MAX_TIMELAPSE_FRAMES


# ---------------------------------------------------------------------------
# frames_to_animation
# ---------------------------------------------------------------------------


def test_frames_to_animation_round_trips_pixel_count():
    frames = [
        np.full((4, 4, 4), v, dtype=np.uint8) for v in (10, 20, 30)
    ]
    animation = frames_to_animation(frames, fps=24)
    assert animation.frame_count == 3
    assert animation.fps == 24
    # Each Animation frame holds the corresponding input pixels.
    for source, frame in zip(frames, animation.frames, strict=True):
        composite = frame.document.composite()
        np.testing.assert_array_equal(composite, source)


def test_frames_to_animation_rejects_empty_input():
    with pytest.raises(ValueError):
        frames_to_animation([], fps=12)


def test_frames_to_animation_rejects_bad_fps():
    frames = [np.zeros((4, 4, 4), dtype=np.uint8)]
    with pytest.raises(ValueError):
        frames_to_animation(frames, fps=0)


def test_frames_to_animation_rejects_blank_name():
    frames = [np.zeros((4, 4, 4), dtype=np.uint8)]
    with pytest.raises(ValueError):
        frames_to_animation(frames, fps=12, name="   ")


def test_frames_to_animation_rejects_non_rgba():
    frames = [np.zeros((4, 4, 3), dtype=np.uint8)]
    with pytest.raises(ValueError):
        frames_to_animation(frames, fps=12)


def test_frames_to_animation_duration_matches_fps():
    frames = [np.zeros((4, 4, 4), dtype=np.uint8)]
    animation = frames_to_animation(frames, fps=10)
    # 1000 / 10 = 100 ms per frame.
    assert animation.frames[0].duration_ms == 100
