"""Tests for the lazy filmstrip / deep-zoom-preview thumbnail loading.

The filmstrip and the low-res deep-zoom loading preview both read their pixmaps
from ``tile_cache``. Some paths into single-image view never run the tile-wall
loader that fills it (opening a file directly, a folder auto-refresh while
zoomed), so the cache is cold and those overlays render blank. ``tile_loader``
now requests the missing thumbnail on demand; these tests pin the dedup policy
and the generation-checked landing without a Qt widget or GL context.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.gpu_image_view import tile_loader
from Imervue.gpu_image_view.tile_loader import (
    discard_tile_worker,
    ensure_filmstrip_thumbnail,
    needs_filmstrip_thumbnail,
    on_filmstrip_thumbnail_loaded,
    tile_grid_needs_reload,
    track_tile_worker,
)


# ---------------------------------------------------------------
# Fakes — keep the workers and pool off the real thread pool so the
# logic is deterministic and Qt-free.
# ---------------------------------------------------------------
class _FakeSignal:
    def __init__(self) -> None:
        self.connected: list = []

    def connect(self, fn) -> None:
        self.connected.append(fn)


class _FakeWorker:
    created: list = []

    def __init__(self, path, size, generation) -> None:
        self.path = path
        self.size = size
        self.generation = generation
        self.signals = SimpleNamespace(finished=_FakeSignal())
        _FakeWorker.created.append(self)


class _FakePool:
    def __init__(self) -> None:
        self.started: list = []

    def start(self, worker, *args) -> None:
        self.started.append(worker)


def _fake_view(images, *, generation=1, cache=None, pending=None,
               thumbnail_size=256):
    cache = {} if cache is None else cache
    pending = set() if pending is None else pending
    view = SimpleNamespace(
        tile_cache=cache,
        _filmstrip_pending=pending,
        model=SimpleNamespace(images=list(images)),
        thumbnail_size=thumbnail_size,
        _load_generation=generation,
        active_tile_workers=set(),
        thumbnail_pool=_FakePool(),
        _tile_load_times={},
        _overlay=SimpleNamespace(ensure_fade_pump=lambda: None),
    )
    view.update = lambda: None
    view._on_filmstrip_thumbnail_loaded = (
        lambda img, path, gen: on_filmstrip_thumbnail_loaded(view, img, path, gen)
    )
    return view


@pytest.fixture(autouse=True)
def _reset_worker(monkeypatch):
    _FakeWorker.created = []
    monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _FakeWorker)


# ---------------------------------------------------------------
# needs_filmstrip_thumbnail — the pure dedup / staleness policy
# ---------------------------------------------------------------
class TestNeedsFilmstripThumbnail:
    def test_missing_path_in_list_needs_load(self):
        assert needs_filmstrip_thumbnail("a.png", {}, set(), ["a.png"]) is True

    def test_falsy_path_is_skipped(self):
        assert needs_filmstrip_thumbnail("", {}, set(), [""]) is False
        assert needs_filmstrip_thumbnail(None, {}, set(), ["a.png"]) is False

    def test_already_cached_is_skipped(self):
        assert needs_filmstrip_thumbnail(
            "a.png", {"a.png": object()}, set(), ["a.png"]) is False

    def test_already_in_flight_is_skipped(self):
        assert needs_filmstrip_thumbnail(
            "a.png", {}, {"a.png"}, ["a.png"]) is False

    def test_path_not_in_list_is_stale_skip(self):
        # A paint that lingered after the folder changed must not load a path
        # that no longer belongs to the viewer's list.
        assert needs_filmstrip_thumbnail("gone.png", {}, set(), ["a.png"]) is False


# ---------------------------------------------------------------
# ensure_filmstrip_thumbnail — spawns at most one worker per path
# ---------------------------------------------------------------
class TestEnsureFilmstripThumbnail:
    def test_spawns_one_worker_for_a_cold_path(self):
        view = _fake_view(["a.png"], generation=4, thumbnail_size=128)
        ensure_filmstrip_thumbnail(view, "a.png")
        assert len(_FakeWorker.created) == 1
        worker = _FakeWorker.created[0]
        assert (worker.path, worker.size, worker.generation) == ("a.png", 128, 4)
        assert "a.png" in view._filmstrip_pending
        assert view.thumbnail_pool.started == [worker]
        assert view.active_tile_workers == {worker}
        # The landing callback is wired so the result reaches tile_cache; the
        # second connection is the self-eviction wired by track_tile_worker.
        assert view._on_filmstrip_thumbnail_loaded in worker.signals.finished.connected
        assert len(worker.signals.finished.connected) == 2

    def test_second_request_while_in_flight_is_deduped(self):
        view = _fake_view(["a.png"])
        ensure_filmstrip_thumbnail(view, "a.png")
        ensure_filmstrip_thumbnail(view, "a.png")
        assert len(_FakeWorker.created) == 1

    def test_cached_path_spawns_nothing(self):
        view = _fake_view(["a.png"], cache={"a.png": object()})
        ensure_filmstrip_thumbnail(view, "a.png")
        assert _FakeWorker.created == []
        assert view._filmstrip_pending == set()

    def test_path_not_in_list_spawns_nothing(self):
        view = _fake_view(["a.png"])
        ensure_filmstrip_thumbnail(view, "stale.png")
        assert _FakeWorker.created == []


# ---------------------------------------------------------------
# on_filmstrip_thumbnail_loaded — clear marker + generation-checked land
# ---------------------------------------------------------------
class TestOnFilmstripThumbnailLoaded:
    def test_landing_populates_cache_and_clears_pending(self):
        view = _fake_view(["a.png"], generation=2, pending={"a.png"})
        img = object()
        on_filmstrip_thumbnail_loaded(view, img, "a.png", 2)
        assert view.tile_cache["a.png"] is img
        assert "a.png" not in view._filmstrip_pending

    def test_stale_generation_is_rejected_but_marker_cleared(self):
        view = _fake_view(["a.png"], generation=5, pending={"a.png"})
        on_filmstrip_thumbnail_loaded(view, object(), "a.png", 4)
        assert "a.png" not in view.tile_cache
        # Marker is cleared so the path can be re-requested under the new
        # generation on the next paint instead of being stuck.
        assert "a.png" not in view._filmstrip_pending

    def test_path_removed_from_list_is_rejected(self):
        view = _fake_view(["a.png"], generation=2, pending={"gone.png"})
        on_filmstrip_thumbnail_loaded(view, object(), "gone.png", 2)
        assert "gone.png" not in view.tile_cache
        assert "gone.png" not in view._filmstrip_pending

    def test_request_then_load_round_trip(self):
        view = _fake_view(["a.png"], generation=3)
        ensure_filmstrip_thumbnail(view, "a.png")
        assert "a.png" in view._filmstrip_pending
        worker = _FakeWorker.created[0]
        img = object()
        # Fire the wired callback exactly as the worker would.
        worker.signals.finished.connected[0](img, "a.png", worker.generation)
        assert view.tile_cache["a.png"] is img
        assert view._filmstrip_pending == set()


# ---------------------------------------------------------------
# tile_grid_needs_reload — the cold-cache guard for entering grid mode
# ---------------------------------------------------------------
class TestTileGridNeedsReload:
    def test_empty_folder_never_reloads(self):
        # A blank wall is the correct result for an empty folder.
        assert tile_grid_needs_reload({}, []) is False
        assert tile_grid_needs_reload({"a.png": object()}, []) is False

    def test_fully_cached_does_not_reload(self):
        cache = {"a.png": object(), "b.png": object()}
        assert tile_grid_needs_reload(cache, ["a.png", "b.png"]) is False

    def test_cold_cache_needs_reload(self):
        # Reaching grid mode after the cache was cleared (open-file -> Esc).
        assert tile_grid_needs_reload({}, ["a.png", "b.png"]) is True

    def test_partially_warmed_cache_needs_reload(self):
        # The filmstrip lazy-loader pre-warms a few neighbours, leaving the rest
        # cold — the wall must still reload so it isn't a sea of placeholders.
        cache = {"a.png": object()}
        assert tile_grid_needs_reload(cache, ["a.png", "b.png", "c.png"]) is True

    def test_single_missing_image_needs_reload(self):
        cache = {"a.png": object(), "c.png": object()}
        assert tile_grid_needs_reload(cache, ["a.png", "b.png", "c.png"]) is True


# ---------------------------------------------------------------
# track_tile_worker / discard_tile_worker — the in-flight set self-evicts on
# finish so a completed worker isn't retained until the next folder switch.
# ---------------------------------------------------------------
class TestTrackTileWorker:
    def test_track_adds_worker_and_wires_eviction(self):
        view = _fake_view(["a.png"])
        worker = _FakeWorker("a.png", 256, 1)
        track_tile_worker(view, worker)
        assert worker in view.active_tile_workers
        # One eviction slot is wired so the set drops the worker on finish.
        assert len(worker.signals.finished.connected) == 1

    def test_discard_removes_tracked_worker(self):
        view = _fake_view(["a.png"])
        worker = _FakeWorker("a.png", 256, 1)
        view.active_tile_workers.add(worker)
        discard_tile_worker(view, worker)
        assert worker not in view.active_tile_workers

    def test_discard_untracked_worker_is_noop(self):
        # A late eviction landing after a folder switch rebuilt the set must be
        # a harmless no-op (set.discard), not a KeyError (list.remove would
        # raise). Discarding twice is also safe.
        view = _fake_view(["a.png"])
        worker = _FakeWorker("a.png", 256, 1)
        discard_tile_worker(view, worker)
        discard_tile_worker(view, worker)
        assert worker not in view.active_tile_workers


class TestTileWorkerSelfEviction:
    """The wired eviction fires on the real ``finished`` signal, so the set
    stays bounded to in-flight workers instead of leaking one per thumbnail."""

    def test_finished_signal_evicts_worker(self, qapp):
        from PySide6.QtCore import QObject, Signal

        class _RealSignals(QObject):
            finished = Signal(object, str, int)

        class _RealWorker:  # hashable (SimpleNamespace defines __eq__ → unhashable)
            def __init__(self) -> None:
                self.signals = _RealSignals()

        view = SimpleNamespace(active_tile_workers=set())
        worker = _RealWorker()
        track_tile_worker(view, worker)
        assert worker in view.active_tile_workers
        # Same-thread direct connection runs the eviction synchronously on emit.
        worker.signals.finished.emit(None, "a.png", 0)
        assert worker not in view.active_tile_workers
