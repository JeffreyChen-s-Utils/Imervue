"""Tests for the per-workload worker-pool sizing policy.

Pure-Python — no Qt. The viewer wires three ``QThreadPool``s
sized by :func:`worker_pool_sizes`; tests here cover the policy
without spawning live thread pools.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.worker_pools import (
    MAX_DEEPZOOM_WORKERS,
    MAX_PREFETCH_WORKERS,
    MAX_PRIORITY,
    MAX_THUMBNAIL_WORKERS,
    MIN_DEEPZOOM_WORKERS,
    MIN_PREFETCH_WORKERS,
    MIN_PRIORITY,
    MIN_THUMBNAIL_WORKERS,
    priority_for_distance,
    worker_pool_sizes,
)


def test_returns_three_named_pools():
    """Every call must produce all three sizes — the viewer's
    init unpacks them; a missing key would crash app startup."""
    sizes = worker_pool_sizes(4)
    assert set(sizes.keys()) == {"thumbnail", "deepzoom", "prefetch"}


def test_single_core_machine_still_makes_progress():
    """A 1-core machine has to make progress — every pool's
    minimum is ≥ 1 so the user isn't stuck at zero workers."""
    sizes = worker_pool_sizes(1)
    assert sizes["thumbnail"] >= MIN_THUMBNAIL_WORKERS
    assert sizes["deepzoom"] >= MIN_DEEPZOOM_WORKERS
    assert sizes["prefetch"] >= MIN_PREFETCH_WORKERS


def test_zero_or_negative_cpu_count_treated_as_one():
    """Defensive: ``os.cpu_count()`` can return ``None`` (the
    caller passes ``or 4``, but other paths might not). The
    helper must clamp rather than divide by garbage."""
    assert worker_pool_sizes(0)["thumbnail"] == MIN_THUMBNAIL_WORKERS
    assert worker_pool_sizes(-5)["thumbnail"] == MIN_THUMBNAIL_WORKERS


def test_thumbnail_pool_scales_with_cores():
    """More cores → more thumbnail parallelism, until the
    ceiling. A folder of 1000 thumbnails benefits visibly."""
    small = worker_pool_sizes(2)["thumbnail"]
    big = worker_pool_sizes(16)["thumbnail"]
    assert small < big or big == MAX_THUMBNAIL_WORKERS


def test_thumbnail_pool_caps_at_ceiling():
    """Past 8-ish cores the I/O backend tops out — don't waste
    threads on diminishing returns."""
    sizes = worker_pool_sizes(64)
    assert sizes["thumbnail"] == MAX_THUMBNAIL_WORKERS


def test_deepzoom_pool_caps_at_ceiling():
    """Deep-zoom is memory-heavy — even on 64 cores we don't
    want 16 parallel pyramids in flight."""
    sizes = worker_pool_sizes(64)
    assert sizes["deepzoom"] == MAX_DEEPZOOM_WORKERS


def test_prefetch_pool_never_exceeds_two():
    """Prefetch is 'spare cycles' — it must not be able to
    starve the foreground even on huge machines."""
    for cores in (1, 4, 16, 64, 128):
        assert worker_pool_sizes(cores)["prefetch"] <= MAX_PREFETCH_WORKERS


def test_prefetch_strictly_smaller_than_thumbnail():
    """Folder open should always be more responsive than
    prefetching neighbours."""
    sizes = worker_pool_sizes(8)
    assert sizes["prefetch"] < sizes["thumbnail"]


def test_deepzoom_strictly_smaller_than_thumbnail_on_typical_cpu():
    """A typical laptop (4-8 cores) — thumbnail gets the bigger
    pool because folder-open bursts are the common bottleneck."""
    for cores in (4, 6, 8):
        sizes = worker_pool_sizes(cores)
        assert sizes["deepzoom"] <= sizes["thumbnail"]


@pytest.mark.parametrize("cores", [1, 2, 4, 8, 12, 16, 32, 64])
def test_all_sizes_in_documented_bounds(cores):
    """No matter the input, every pool stays inside its
    documented MIN_/MAX_ window — protects future tuning from
    accidentally publishing an out-of-range number."""
    sizes = worker_pool_sizes(cores)
    assert MIN_THUMBNAIL_WORKERS <= sizes["thumbnail"] <= MAX_THUMBNAIL_WORKERS
    assert MIN_DEEPZOOM_WORKERS <= sizes["deepzoom"] <= MAX_DEEPZOOM_WORKERS
    assert MIN_PREFETCH_WORKERS <= sizes["prefetch"] <= MAX_PREFETCH_WORKERS


def test_total_workers_does_not_exceed_2x_cores_on_modest_cpus():
    """Combined ceiling sanity — on a 4-core machine the total
    should stay reasonable (won't ramp up to oversubscription
    that hurts the GUI thread)."""
    sizes = worker_pool_sizes(4)
    total = sum(sizes.values())
    assert total <= 4 * 2


def test_min_max_constants_form_valid_ranges():
    """Floor ≤ ceiling on every pool — guards against a future
    tuning typo."""
    assert MIN_THUMBNAIL_WORKERS <= MAX_THUMBNAIL_WORKERS
    assert MIN_DEEPZOOM_WORKERS <= MAX_DEEPZOOM_WORKERS
    assert MIN_PREFETCH_WORKERS <= MAX_PREFETCH_WORKERS


# ---------------------------------------------------------------
# priority_for_distance
# ---------------------------------------------------------------


def test_priority_distance_zero_is_max():
    """The current image itself — highest priority. The pool
    pulls it ahead of every neighbour."""
    assert priority_for_distance(0) == MAX_PRIORITY


def test_priority_decreases_with_distance():
    """Each step away from the current image drops priority by
    1, so the worker pool drains by distance."""
    p1 = priority_for_distance(1)
    p2 = priority_for_distance(2)
    p3 = priority_for_distance(3)
    assert MAX_PRIORITY > p1 > p2 > p3


def test_priority_symmetric_for_signed_distance():
    """Index 5 vs index 15 around current=10 — both are distance
    5, both should get the same priority. Direction is the
    prefetch policy's job."""
    assert priority_for_distance(5) == priority_for_distance(-5)


def test_priority_clamps_to_min_for_huge_distances():
    """A 10 000-image folder must not produce -9999 priorities —
    SQLite-style integer overflow risks aside, the QThreadPool
    only cares about *order*; flooring at MIN_PRIORITY keeps the
    range tight and predictable."""
    assert priority_for_distance(99999) == MIN_PRIORITY
    assert priority_for_distance(-99999) == MIN_PRIORITY


def test_priority_constants_form_valid_range():
    """MAX > 0 > MIN — guard against a future tuning typo
    that would invert the relationship."""
    assert MAX_PRIORITY > 0 > MIN_PRIORITY


@pytest.mark.parametrize("distance", [0, 1, 2, 3, 5, 10, 25])
def test_priority_in_documented_range(distance):
    """No matter the input, the helper stays inside the
    [MIN, MAX] window the QThreadPool relies on."""
    p = priority_for_distance(distance)
    assert MIN_PRIORITY <= p <= MAX_PRIORITY


def test_priority_distance_one_is_just_below_max():
    """Closest neighbour comes right after the current image —
    they're effectively the same priority bucket from the user's
    perspective."""
    assert priority_for_distance(1) == MAX_PRIORITY - 1
