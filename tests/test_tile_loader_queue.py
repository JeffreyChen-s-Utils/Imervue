"""Loading and cancellation use bounded viewport jobs, including filmstrip retries."""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QMutex

from Imervue.gpu_image_view import tile_loader
from tests.test_tile_loader import _FakeWorker, _fake_view


@pytest.fixture
def queued_view(monkeypatch):
    _FakeWorker.created = []
    monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _FakeWorker)
    view = _fake_view([str(i) for i in range(100_000)])
    view.width = lambda: 500
    view.height = lambda: 300
    view.devicePixelRatio = lambda: 1.
    view.tile_scale = 1.
    view.tile_padding = 8
    view.grid_offset_x = 0.
    view.grid_offset_y = -5_000_000.
    view.grid_mutex = QMutex()
    view.thumbnail_pool.maxThreadCount = lambda: 2
    view._tile_max_dimensions = (0, 0)
    view.tile_grid_mode = True
    view._on_thumbnail_error = lambda path, message, gen: tile_loader.on_thumbnail_error(
        view, path, message, gen)
    tile_loader._spawn_thumbnail_workers(view, 1)
    return view


def _finish(view, worker):
    array = np.ones((20, 32, 4), dtype=np.uint8)
    for callback in tuple(worker.signals.finished.connected):
        callback(array, worker.path, worker.generation)


def test_hundred_thousand_paths_create_only_worker_slots_for_visible_buffer(queued_view):
    view = queued_view
    assert len(_FakeWorker.created) == 2
    assert len(view.active_tile_workers) == 2
    assert all(18_000 < int(worker.path) < 20_000 for worker in view.active_tile_workers)
    assert view._tile_load_total <= 10
    for worker in tuple(view.active_tile_workers):
        _finish(view, worker)
    assert len(view.active_tile_workers) <= 2
    assert len(_FakeWorker.created) <= 4


def test_pan_promotes_new_viewport_before_unstarted_old_rows(queued_view):
    view = queued_view
    old = list(view.active_tile_workers)
    view.grid_offset_y = 0
    tile_loader.pump_thumbnail_workers(view)
    assert len(_FakeWorker.created) == 2
    _finish(view, old[0])
    assert int(_FakeWorker.created[-1].path) < 10
    assert len(view.active_tile_workers) == 2


def test_completed_viewport_does_not_backfill_unvisited_library(queued_view):
    view = queued_view
    for _ in range(20):
        for worker in tuple(view.active_tile_workers):
            _finish(view, worker)
    assert not view.active_tile_workers
    assert len(_FakeWorker.created) <= 10
    assert view._tile_load_count == view._tile_load_total


def test_filmstrip_attaches_to_existing_decode_without_a_duplicate(queued_view):
    view = queued_view
    worker = next(iter(view.active_tile_workers))
    tile_loader.ensure_filmstrip_thumbnail(view, worker.path)
    assert worker.path in view._filmstrip_pending
    _finish(view, worker)
    assert worker.path not in view._filmstrip_pending
    assert sum(w.path == worker.path for w in _FakeWorker.created) == 1


def test_explicit_filmstrip_path_outside_wall_gets_next_free_slot(queued_view):
    view = queued_view
    tile_loader.ensure_filmstrip_thumbnail(view, "99999")
    worker = next(iter(view.active_tile_workers))
    _finish(view, worker)
    requested = _FakeWorker.created[-1]
    assert requested.path == "99999"
    _finish(view, requested)
    assert "99999" in view.tile_cache
    assert "99999" not in view._filmstrip_pending


def test_retired_generation_completion_cannot_pump_new_queue(queued_view):
    view = queued_view
    old = list(view.active_tile_workers)
    view.active_tile_workers.clear()
    view._tile_queue = None
    view._load_generation += 1
    _finish(view, old[0])
    assert not view.tile_cache
    assert len(_FakeWorker.created) == 2


def test_old_filmstrip_result_does_not_clear_current_generation_marker(queued_view):
    view = queued_view
    worker = next(iter(view.active_tile_workers))
    tile_loader.ensure_filmstrip_thumbnail(view, worker.path)
    tile_loader.on_filmstrip_thumbnail_loaded(view, object(), worker.path, 0)
    assert worker.path in view._filmstrip_pending
    assert worker.path not in view.tile_cache
    _finish(view, worker)
    assert worker.path not in view._filmstrip_pending


def test_force_retry_preserves_valid_cache_until_new_result_and_deduplicates(queued_view):
    view = queued_view
    view.tile_cache["99999"] = np.zeros((20, 32, 4), dtype=np.uint8)
    view.tile_errors["99999"] = "failed"
    tile_loader._retry_thumbnail(view, "99999", 1)
    tile_loader._retry_thumbnail(view, "99999", 1)
    assert view.tile_cache["99999"][0, 0, 0] == 0
    _finish(view, next(iter(view.active_tile_workers)))
    worker = _FakeWorker.created[-1]
    assert worker.path == "99999"
    _finish(view, worker)
    assert view.tile_cache["99999"][0, 0, 0] == 1
    assert sum(w.path == "99999" for w in _FakeWorker.created) == 1


def test_permanent_error_finishes_pending_filmstrip_and_does_not_auto_loop(queued_view):
    view = queued_view
    worker = next(iter(view.active_tile_workers))
    tile_loader.ensure_filmstrip_thumbnail(view, worker.path)
    tile_loader.on_thumbnail_error(view, worker.path, "invalid pixels", 1)
    tile_loader.discard_tile_worker(view, worker)
    assert worker.path not in view._filmstrip_pending
    assert worker.path in view.tile_errors
    assert sum(w.path == worker.path for w in _FakeWorker.created) == 1


def test_zero_pool_size_is_clamped_and_missing_urgent_path_is_discarded(monkeypatch):
    _FakeWorker.created = []
    monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _FakeWorker)
    view = _fake_view(["a"])
    view.thumbnail_pool.maxThreadCount = lambda: 0
    tile_loader._spawn_thumbnail_workers(view, 1)
    assert len(_FakeWorker.created) == 1
    view.tile_cache["a"] = object()
    view._tile_queue.request("stale")
    tile_loader.discard_tile_worker(view, next(iter(view.active_tile_workers)))
    assert "stale" not in view._tile_queue.urgent


def test_retry_while_active_deduplicates_but_rewrite_requires_one_fresh_decode(queued_view):
    view = queued_view
    worker = next(iter(view.active_tile_workers))
    tile_loader._retry_thumbnail(view, worker.path, 1)
    assert worker.path not in view._tile_queue.urgent
    tile_loader.refresh_rewritten_tile(view, worker.path, 1)
    assert worker.path in view._tile_queue.urgent
    _finish(view, worker)
    assert sum(w.path == worker.path for w in _FakeWorker.created) == 2
