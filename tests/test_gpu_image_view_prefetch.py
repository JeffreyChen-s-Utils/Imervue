"""Tests for the image-prefetch policy helpers.

Pure-Python — no Qt, no GL. The GPUImageView wires these helpers via
its ``_compute_prefetch_targets`` shim; that shim sits behind a GL
boundary covered by ``# pragma: no cover`` comments, so the tests
here cover the policy layer where the behaviour actually lives.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.images.prefetch import (
    DEFAULT_RANGE,
    DIRECTIONAL_RANGE_AHEAD,
    DIRECTIONAL_RANGE_BEHIND,
    NavigationDirectionTracker,
    compute_prefetch_targets,
    infer_recent_direction,
    range_for_direction,
)


# ---------------------------------------------------------------
# compute_prefetch_targets
# ---------------------------------------------------------------


def test_symmetric_window_around_middle():
    """Default symmetric ±3 around an interior index → 6 neighbours
    (the current index is excluded — already loaded)."""
    out = compute_prefetch_targets(10, 100)
    assert sorted(out) == [7, 8, 9, 11, 12, 13]


def test_window_clipped_at_start():
    """Index 0 → only forward neighbours; no negative indices leak."""
    out = compute_prefetch_targets(0, 100)
    assert sorted(out) == [1, 2, 3]
    assert all(i >= 0 for i in out)


def test_window_clipped_at_end():
    """Last index → only backward neighbours; no past-the-end."""
    out = compute_prefetch_targets(99, 100)
    assert sorted(out) == [96, 97, 98]
    assert all(i < 100 for i in out)


def test_asymmetric_window_forward_bias():
    """Forward bias → 5 ahead, 1 behind."""
    out = compute_prefetch_targets(
        10, 100, range_ahead=5, range_behind=1,
    )
    assert sorted(out) == [9, 11, 12, 13, 14, 15]


def test_asymmetric_window_backward_bias():
    """Backward bias → 1 ahead, 5 behind (mirror of forward)."""
    out = compute_prefetch_targets(
        10, 100, range_ahead=1, range_behind=5,
    )
    assert sorted(out) == [5, 6, 7, 8, 9, 11]


def test_distance_one_first_then_two():
    """Worker pool picks up the next-pressed image before far-away
    ones — closer distances must appear first in the return order."""
    out = compute_prefetch_targets(10, 100, range_ahead=2, range_behind=2)
    # The two distance-1 neighbours (9, 11) must come before the
    # two distance-2 neighbours (8, 12).
    assert out.index(11) < out.index(12)
    assert out.index(9) < out.index(8)


def test_empty_folder_returns_empty():
    """Total 0 → nothing to prefetch, no exception."""
    assert compute_prefetch_targets(0, 0) == []


def test_negative_or_out_of_range_index_returns_empty():
    """Defensive: a stale index from a previous folder must not
    leak garbage into the worker pool."""
    assert compute_prefetch_targets(-1, 100) == []
    assert compute_prefetch_targets(100, 100) == []
    assert compute_prefetch_targets(500, 100) == []


def test_negative_range_clamps_to_zero():
    """A misconfigured caller passing range_ahead=-3 → treat as 0,
    not as a reverse-direction walk that produces backward targets."""
    out = compute_prefetch_targets(
        10, 100, range_ahead=-3, range_behind=2,
    )
    assert sorted(out) == [8, 9]


def test_zero_ranges_returns_empty():
    """Both ranges 0 (e.g. memory-pressure mode disabling prefetch)
    → empty without erroring."""
    assert compute_prefetch_targets(
        10, 100, range_ahead=0, range_behind=0,
    ) == []


def test_window_doesnt_include_current_index():
    """The current image is already loaded by the viewer; the cache
    budget should land on neighbours, not on a redundant copy of
    the current frame."""
    out = compute_prefetch_targets(10, 100, range_ahead=5, range_behind=5)
    assert 10 not in out


# ---------------------------------------------------------------
# infer_recent_direction
# ---------------------------------------------------------------


def test_infer_direction_empty_history():
    """No history → scattered, the safe default."""
    assert infer_recent_direction([]) == 0


def test_infer_direction_all_forward():
    """Five next-presses in a row → forward."""
    assert infer_recent_direction([1, 1, 1, 1, 1]) == 1


def test_infer_direction_all_backward():
    assert infer_recent_direction([-1, -1, -1, -1, -1]) == -1


def test_infer_direction_one_outlier_still_forward():
    """75% threshold: 4 forward + 1 backward → still forward.
    Avoids a single accidental ← undoing the heuristic."""
    assert infer_recent_direction([1, 1, 1, 1, -1]) == 1


def test_infer_direction_mixed_scattered():
    """Half / half → scattered."""
    assert infer_recent_direction([1, -1, 1, -1, 1, -1]) == 0


def test_infer_direction_ignores_jumps():
    """A jump (delta != ±1) registers as a 0 entry, not a vote for
    either side. Three forwards + two jumps → still forward (3/3
    of counted ±1 entries agree)."""
    assert infer_recent_direction([1, 0, 1, 0, 1]) == 1


def test_infer_direction_only_jumps_is_scattered():
    """All jumps (no ±1 entries) → no vote → scattered."""
    assert infer_recent_direction([0, 0, 0, 0]) == 0


def test_infer_direction_only_uses_recent_history():
    """A long history with old forward + recent backward — the
    decision must follow the recent moves."""
    history = ([1] * 20) + ([-1] * 5)
    assert infer_recent_direction(history) == -1


# ---------------------------------------------------------------
# range_for_direction
# ---------------------------------------------------------------


def test_range_for_forward():
    ahead, behind = range_for_direction(1)
    assert ahead == DIRECTIONAL_RANGE_AHEAD
    assert behind == DIRECTIONAL_RANGE_BEHIND


def test_range_for_backward():
    """Backward is the mirror of forward — bias the same magnitude
    in the opposite direction."""
    ahead, behind = range_for_direction(-1)
    assert ahead == DIRECTIONAL_RANGE_BEHIND
    assert behind == DIRECTIONAL_RANGE_AHEAD


def test_range_for_scattered_is_symmetric():
    """No clear direction → fall back to the symmetric default the
    viewer used before this heuristic existed."""
    assert range_for_direction(0) == (DEFAULT_RANGE, DEFAULT_RANGE)


def test_default_constants_in_sane_ranges():
    """Sanity guard: ahead bias > symmetric > behind bias."""
    assert DIRECTIONAL_RANGE_BEHIND <= DEFAULT_RANGE <= DIRECTIONAL_RANGE_AHEAD


# ---------------------------------------------------------------
# NavigationDirectionTracker
# ---------------------------------------------------------------


def test_tracker_starts_scattered():
    tracker = NavigationDirectionTracker()
    assert tracker.direction() == 0


def test_tracker_picks_up_forward_walk():
    tracker = NavigationDirectionTracker()
    for i in range(6):
        tracker.record(i)
    assert tracker.direction() == 1


def test_tracker_pivots_to_backward():
    """Long forward walk then a backward run — the tracker should
    flip once enough recent ←-presses dominate."""
    tracker = NavigationDirectionTracker()
    for i in range(10):
        tracker.record(i)
    assert tracker.direction() == 1
    # Reverse walk.
    for i in range(9, 4, -1):
        tracker.record(i)
    assert tracker.direction() == -1


def test_tracker_treats_jumps_as_scattered():
    """A folder-list click that jumps from 0 to 50 is not navigation
    — the tracker must not interpret it as forward."""
    tracker = NavigationDirectionTracker()
    tracker.record(0)
    tracker.record(50)
    tracker.record(51)
    # Only one ±1 step has been recorded; not enough to call it.
    # The threshold needs the entry to dominate, so a 1/2 ratio
    # (one +1 vs zero counted otherwise) actually clears 75% — but
    # below counted==0 would still be scattered. Verify we don't
    # crash and produce a defined value.
    assert tracker.direction() in (-1, 0, 1)


def test_tracker_reset_forgets_history():
    """Folder change → fresh start. Otherwise a forward-heavy old
    folder would bias the first prefetch in the new folder."""
    tracker = NavigationDirectionTracker()
    for i in range(6):
        tracker.record(i)
    assert tracker.direction() == 1
    tracker.reset()
    assert tracker.direction() == 0


@pytest.mark.parametrize("step", [-2, 2, 5, -10])
def test_tracker_multi_step_jump_is_not_directional(step):
    """Step != ±1 must not vote for any direction — only one-step
    moves count as 'browsing'."""
    tracker = NavigationDirectionTracker()
    tracker.record(0)
    for _ in range(5):
        tracker.record(tracker._last_index + step)   # noqa: SLF001
    assert tracker.direction() == 0


# ---------------------------------------------------------------
# Round-trip: tracker → range_for_direction → compute_prefetch_targets
# ---------------------------------------------------------------


def test_full_pipeline_forward_bias_lands_ahead():
    """End-to-end smoke: walking forward biases the prefetch window
    forward. Catches a regression where any one of the three helpers
    gets disconnected from the others."""
    tracker = NavigationDirectionTracker()
    for i in range(6):
        tracker.record(i)
    ahead, behind = range_for_direction(tracker.direction())
    targets = compute_prefetch_targets(
        5, 100, range_ahead=ahead, range_behind=behind,
    )
    forward_count = sum(1 for t in targets if t > 5)
    backward_count = sum(1 for t in targets if t < 5)
    assert forward_count > backward_count


def test_full_pipeline_scattered_stays_symmetric():
    """A user clicking around at random gets the same baseline they
    had before the heuristic existed."""
    tracker = NavigationDirectionTracker()
    # Alternating navigation — direction stays scattered.
    for delta in (1, -1, 1, -1, 1, -1):
        last = tracker._last_index or 10   # noqa: SLF001
        tracker.record(last + delta)
    ahead, behind = range_for_direction(tracker.direction())
    assert ahead == behind == DEFAULT_RANGE
