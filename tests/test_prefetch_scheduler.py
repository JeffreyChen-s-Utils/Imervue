"""Tests for PrefetchScheduler — deep-zoom neighbour prefetch orchestration.

A fake worker + pool avoid Qt threads; the policy (which indices) is tested
in test_gpu_image_view_prefetch. These tests cover the stateful glue: cache
trim, worker bookkeeping, eviction of out-of-window entries, and cancel-all.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.gpu_image_view import prefetch_scheduler
from Imervue.gpu_image_view.prefetch_scheduler import PrefetchScheduler


class _FakeSignals:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self):
        self._slots.clear()


class _FakeWorker:
    def __init__(self, path, recipe=None):
        self.path = path
        self.signals = SimpleNamespace(finished=_FakeSignals())
        self.aborted = False

    def abort(self):
        self.aborted = True


class _FakePool:
    def __init__(self):
        self.started = []

    def start(self, worker, priority=0):
        self.started.append((worker, priority))


def _make_view(images, current=0):
    return SimpleNamespace(
        model=SimpleNamespace(images=list(images)),
        current_index=current,
        prefetch_pool=_FakePool(),
        deep_zoom=None,
        tile_manager=None,
        updated=0,
        _on_prefetch_loaded=lambda dzi, path: None,
    )


@pytest.fixture(autouse=True)
def _patch_worker_and_recipe(monkeypatch):
    from Imervue.image.recipe_store import recipe_store
    monkeypatch.setattr(prefetch_scheduler, "LoadDeepZoomWorker", _FakeWorker)
    monkeypatch.setattr(recipe_store, "get_for_path", lambda p: None)


def test_schedule_empty_folder_noop():
    view = _make_view([])
    sched = PrefetchScheduler(view)
    sched.schedule()
    assert view.prefetch_pool.started == []


def test_schedule_spawns_neighbour_workers():
    images = [f"img{i}.png" for i in range(20)]
    view = _make_view(images, current=10)
    sched = PrefetchScheduler(view)
    sched.schedule()
    # Symmetric ±3 around index 10 (current excluded) → 6 workers.
    assert len(view.prefetch_pool.started) == 6
    assert all(isinstance(w, _FakeWorker) for w, _ in view.prefetch_pool.started)


def test_store_trims_to_max():
    view = _make_view(["a"])
    sched = PrefetchScheduler(view)
    for i in range(prefetch_scheduler.PREFETCH_MAX + 3):
        sched.store(f"p{i}", object())
    assert len(sched.cache) == prefetch_scheduler.PREFETCH_MAX
    # Oldest entries evicted first (FIFO).
    assert "p0" not in sched.cache


def test_take_and_has_and_discard():
    sched = PrefetchScheduler(_make_view(["a"]))
    obj = object()
    sched.store("a", obj)
    assert sched.has("a") is True
    assert sched.take("a") is obj
    assert sched.has("a") is False
    sched.store("b", object())
    sched.discard("b")
    assert sched.has("b") is False
    # Discarding a missing key is safe.
    sched.discard("missing")


def test_cancel_all_clears_state_and_aborts():
    images = [f"img{i}.png" for i in range(20)]
    view = _make_view(images, current=10)
    sched = PrefetchScheduler(view)
    sched.schedule()
    workers = list(sched.workers.values())
    sched.store("cached", object())
    sched.cancel_all()
    assert sched.workers == {}
    assert sched.cache == {}
    assert all(w.aborted for w in workers)


def test_evict_outdated_cache_on_reschedule():
    images = [f"img{i}.png" for i in range(20)]
    view = _make_view(images, current=10)
    sched = PrefetchScheduler(view)
    # Pre-seed a far-away cache entry that the new window won't include.
    sched.store("img0.png", object())
    sched.schedule()
    assert "img0.png" not in sched.cache


def test_spawn_skips_already_cached_or_inflight():
    images = [f"img{i}.png" for i in range(20)]
    view = _make_view(images, current=10)
    sched = PrefetchScheduler(view)
    # Cache one neighbour so it isn't re-spawned.
    sched.cache["img11.png"] = object()
    sched.schedule()
    started_paths = {w.path for w, _ in view.prefetch_pool.started}
    assert "img11.png" not in started_paths
