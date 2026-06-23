"""Tests for develop-edit undo coalescing."""
from __future__ import annotations

from Imervue.gpu_image_view.actions.undo_coalescer import (
    EditEvent,
    coalesce_edits,
    compress_history,
    drop_noop_edits,
)


# ---------------------------------------------------------------------------
# coalesce_edits
# ---------------------------------------------------------------------------


def test_empty_and_single():
    assert coalesce_edits([]) == []
    one = [EditEvent("brightness", 0.0, 0.2, 1.0)]
    assert coalesce_edits(one) == one


def test_merges_same_field_within_window():
    events = [
        EditEvent("brightness", 0.0, 0.1, 1.0),
        EditEvent("brightness", 0.1, 0.2, 1.2),
        EditEvent("brightness", 0.2, 0.5, 1.4),
    ]
    merged = coalesce_edits(events, window=0.5)
    assert merged == [EditEvent("brightness", 0.0, 0.5, 1.0)]


def test_gap_beyond_window_splits():
    events = [
        EditEvent("brightness", 0.0, 0.1, 1.0),
        EditEvent("brightness", 0.1, 0.2, 5.0),  # 4s later
    ]
    merged = coalesce_edits(events, window=0.5)
    assert len(merged) == 2


def test_different_field_splits():
    events = [
        EditEvent("brightness", 0.0, 0.1, 1.0),
        EditEvent("contrast", 0.0, 0.3, 1.1),
    ]
    assert coalesce_edits(events) == events


def test_interleaved_runs_grouped_separately():
    events = [
        EditEvent("brightness", 0.0, 0.1, 1.0),
        EditEvent("brightness", 0.1, 0.2, 1.1),
        EditEvent("contrast", 0.0, 0.4, 1.2),
        EditEvent("brightness", 0.2, 0.6, 1.3),
    ]
    merged = coalesce_edits(events, window=0.5)
    assert [(e.field, e.old, e.new) for e in merged] == [
        ("brightness", 0.0, 0.2),
        ("contrast", 0.0, 0.4),
        ("brightness", 0.2, 0.6),
    ]


def test_does_not_mutate_input():
    events = [
        EditEvent("brightness", 0.0, 0.1, 1.0),
        EditEvent("brightness", 0.1, 0.2, 1.2),
    ]
    before = list(events)
    coalesce_edits(events)
    assert events == before


# ---------------------------------------------------------------------------
# drop_noop_edits / compress_history
# ---------------------------------------------------------------------------


def test_drop_noop_edits():
    events = [
        EditEvent("brightness", 0.0, 0.0, 1.0),  # no-op
        EditEvent("contrast", 0.0, 0.3, 1.1),
    ]
    assert drop_noop_edits(events) == [EditEvent("contrast", 0.0, 0.3, 1.1)]


def test_compress_history_drops_drag_out_and_back():
    # Dragged a slider away and back to its original value -> nothing net.
    events = [
        EditEvent("exposure", 0.0, 0.5, 1.0),
        EditEvent("exposure", 0.5, 1.0, 1.1),
        EditEvent("exposure", 1.0, 0.0, 1.2),
    ]
    assert compress_history(events, window=0.5) == []


def test_compress_history_keeps_net_change():
    events = [
        EditEvent("exposure", 0.0, 0.5, 1.0),
        EditEvent("exposure", 0.5, 1.0, 1.1),
    ]
    assert compress_history(events, window=0.5) == [
        EditEvent("exposure", 0.0, 1.0, 1.0)]
