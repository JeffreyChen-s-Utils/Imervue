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
    images_changed,
    needs_filmstrip_thumbnail,
    on_thumbnail_error,
    on_filmstrip_thumbnail_loaded,
    reset_view_memory_on_switch,
    sync_tile_grid_incremental,
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


class _FakeImageModel:
    def __init__(self, images):
        self.images = list(images)

    def set_images(self, paths):
        self.images = list(paths)


def _fake_view(images, *, generation=1, cache=None, pending=None,
               thumbnail_size=256):
    cache = {} if cache is None else cache
    pending = set() if pending is None else pending
    view = SimpleNamespace(
        tile_cache=cache,
        _filmstrip_pending=pending,
        model=_FakeImageModel(images),
        thumbnail_size=thumbnail_size,
        _load_generation=generation,
        active_tile_workers=set(),
        thumbnail_pool=_FakePool(),
        _tile_load_times={},
        _tile_file_signatures={},
        _overlay=SimpleNamespace(ensure_fade_pump=lambda: None),
        tile_errors={},
        offline_paths=set(),
        selected_tiles=set(),
        focused_tile_index=0,
        current_index=0,
        tile_textures={},
        _tile_tex_sizes={},
        _vram_usage=0,
        _filmstrip_thumb_cache={},
        _tile_error_toasted=set(),
        main_window=SimpleNamespace(),
        _progress_coalescer=SimpleNamespace(schedule=lambda: None, force_flush=lambda: None),
    )
    view.update = lambda: None
    view._cancel_tile_workers = lambda: None
    view._on_thumbnail_loaded = lambda img, path, gen: tile_loader.on_thumbnail_loaded(
        view, img, path, gen,
    )
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


class TestThumbnailError:
    def test_records_visible_error_for_current_generation(self):
        view = _fake_view(["bad.png"], generation=3)
        on_thumbnail_error(view, "bad.png", "decode failed", 3)
        assert view.tile_errors["bad.png"] == "decode failed"

    def test_ignores_stale_generation(self):
        view = _fake_view(["bad.png"], generation=3)
        on_thumbnail_error(view, "bad.png", "old", 2)
        assert view.tile_errors == {}


class TestSyncTileGridIncremental:
    def test_keeps_cached_thumbnails_and_loads_only_new_paths(self):
        cached = {"a.png": object()}
        view = _fake_view(["a.png", "b.png"], cache=cached)
        sync_tile_grid_incremental(view, ["a.png", "c.png"])
        assert "a.png" in view.tile_cache
        assert "b.png" not in view.tile_cache
        assert view.model.images == ["a.png", "c.png"]
        assert [w.path for w in _FakeWorker.created] == ["c.png"]

    def test_renamed_file_migrates_cached_thumbnail(self, tmp_path):
        old = tmp_path / "old.png"
        new = tmp_path / "new.png"
        old.write_bytes(b"same image bytes")
        st = old.stat()
        img = object()
        view = _fake_view([str(old)], cache={str(old): img})
        view._tile_file_signatures[str(old)] = (st.st_size, st.st_mtime_ns, ".png")
        old.replace(new)

        sync_tile_grid_incremental(view, [str(new)])

        assert view.tile_cache == {str(new): img}
        assert _FakeWorker.created == []


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


class TestImagesChanged:
    def test_same_list_is_not_a_change(self):
        assert images_changed(["a.png", "b.png"], ["a.png", "b.png"]) is False

    def test_same_list_by_identity(self):
        images = ["a.png", "b.png"]
        assert images_changed(images, images) is False

    def test_different_list_is_a_change(self):
        assert images_changed(["a.png"], ["b.png"]) is True

    def test_reorder_counts_as_change(self):
        assert images_changed(["a.png", "b.png"], ["b.png", "a.png"]) is True

    def test_empty_to_populated_is_a_change(self):
        assert images_changed([], ["a.png"]) is True

    def test_both_empty_is_not_a_change(self):
        assert images_changed([], []) is False


class TestResetViewMemoryOnSwitch:
    @staticmethod
    def _view(images):
        return SimpleNamespace(
            model=SimpleNamespace(images=list(images)),
            _view_memory={"old.png": {"zoom": 3.0, "dx": 5, "dy": 7}},
            _user_locked_view=True,
        )

    def test_folder_switch_clears_memory_and_lock(self):
        view = self._view(["old.png"])
        assert reset_view_memory_on_switch(view, ["new.png"]) is True
        assert view._view_memory == {}
        assert view._user_locked_view is False

    def test_same_folder_reload_keeps_memory_and_lock(self):
        # A thumbnail-size rebuild / cold-cache refill passes the same list, so
        # the user's remembered zoom/pan must survive.
        view = self._view(["old.png"])
        assert reset_view_memory_on_switch(view, ["old.png"]) is False
        assert view._view_memory == {"old.png": {"zoom": 3.0, "dx": 5, "dy": 7}}
        assert view._user_locked_view is True

    def test_switch_to_empty_folder_clears(self):
        view = self._view(["old.png"])
        assert reset_view_memory_on_switch(view, []) is True
        assert view._view_memory == {}
        assert view._user_locked_view is False


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
