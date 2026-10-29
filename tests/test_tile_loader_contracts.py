"""Contract tests for the thumbnail-wall loader's public surface and edge paths.

Pins behaviour the focused ``test_tile_loader*`` suites leave open: the names
callers import from ``tile_loader``, the patch points tests rely on, transient
retry scheduling, failure toasts, a successful landing's bookkeeping, focus and
selection carry-over across an incremental sync, the folder-switch reset and the
offline sweep's issue reporting.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QMutex

from Imervue.gpu_image_view import tile_loader
from tests.test_tile_loader import _FakeSignal, _FakeWorker, _fake_view

_PUBLIC_NAMES = (
    "OFFLINE_SWEEP_INTERVAL_MS", "OfflineScanWorker", "add_thumbnail",
    "discard_tile_worker", "ensure_filmstrip_thumbnail", "file_signature",
    "flush_thumbnail_progress", "image_is_current", "images_changed",
    "load_tile_grid_async", "needs_filmstrip_thumbnail", "on_filmstrip_thumbnail_loaded",
    "on_offline_scan_finished", "on_thumbnail_error", "on_thumbnail_loaded",
    "pump_thumbnail_workers", "refetch_list_rows", "refresh_rewritten_tile",
    "reset_view_memory_on_switch", "scan_folder_paths", "start_offline_sweep",
    "stop_offline_sweep", "sync_tile_grid_incremental", "tick_offline_sweep",
    "tile_grid_needs_reload", "track_tile_worker", "_retry_thumbnail",
    "_spawn_thumbnail_workers",
)


@pytest.fixture(autouse=True)
def _fake_workers(monkeypatch):
    _FakeWorker.created = []
    monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _FakeWorker)


@pytest.fixture
def scheduled(monkeypatch):
    """Capture ``call_later`` in whichever loader module schedules the retry."""
    calls: list = []

    def _capture(ms, owner, fn):
        calls.append((ms, owner, fn))

    for name, module in list(sys.modules.items()):
        if name.startswith("Imervue.gpu_image_view.tile_loader") and hasattr(module, "call_later"):
            monkeypatch.setattr(module, "call_later", _capture)
    return calls


def _toasting_view(images):
    view = _fake_view(images)
    toasts: list = []
    issues: list = []
    view.main_window = SimpleNamespace(
        toast=SimpleNamespace(error=toasts.append),
        language_wrapper=SimpleNamespace(language_word_dict={}),
        record_image_issue=lambda path, message: issues.append((path, message)),
    )
    return view, toasts, issues


class TestPublicSurface:
    @pytest.mark.parametrize("name", _PUBLIC_NAMES)
    def test_name_is_importable_from_tile_loader(self, name):
        assert hasattr(tile_loader, name)

    def test_sweep_interval_is_four_seconds(self):
        assert tile_loader.OFFLINE_SWEEP_INTERVAL_MS == 4000


class TestTransientRetry:
    def test_transient_error_schedules_a_backed_off_retry(self, scheduled):
        view, _toasts, _issues = _toasting_view(["a.png"])
        tile_loader.on_thumbnail_error(view, "a.png", "file is locked", 1)
        assert [(ms, owner) for ms, owner, _fn in scheduled] == [(200, view)]
        assert view._tile_retry_counts == {"a.png": 1}
        scheduled[0][2]()
        assert [w.path for w in _FakeWorker.created] == ["a.png"]
        assert "a.png" not in view.tile_errors

    def test_retries_back_off_and_stop_after_two(self, scheduled):
        view, _toasts, _issues = _toasting_view(["a.png"])
        for _ in range(3):
            tile_loader.on_thumbnail_error(view, "a.png", "resource busy", 1)
        assert [ms for ms, _owner, _fn in scheduled] == [200, 400]
        assert view._tile_retry_counts == {"a.png": 2}

    def test_permanent_error_never_retries(self, scheduled):
        view, _toasts, _issues = _toasting_view(["a.png"])
        tile_loader.on_thumbnail_error(view, "a.png", "invalid pixels", 1)
        assert scheduled == []
        assert view.tile_errors == {"a.png": "invalid pixels"}

    def test_retry_for_a_stale_generation_spawns_nothing(self, scheduled):
        view, _toasts, _issues = _toasting_view(["a.png"])
        tile_loader.on_thumbnail_error(view, "a.png", "locked", 1)
        view._load_generation = 2
        scheduled[0][2]()
        assert _FakeWorker.created == []


class TestFailureReporting:
    def test_failure_toasts_once_per_path_with_the_file_name(self, scheduled):
        view, toasts, issues = _toasting_view(["dir/a.png"])
        tile_loader.on_thumbnail_error(view, "dir/a.png", "bad data", 1)
        tile_loader.on_thumbnail_error(view, "dir/a.png", "bad data", 1)
        assert toasts == ["Couldn't load thumbnail: a.png"]
        assert issues == [("dir/a.png", "bad data")] * 2

    def test_missing_file_records_issue_without_a_toast(self, scheduled):
        view, toasts, issues = _toasting_view(["a.png"])
        view.tile_errors["a.png"] = "old"
        tile_loader.on_thumbnail_error(view, "a.png", "No such file or directory", 1)
        assert toasts == []
        assert view.offline_paths == {"a.png"}
        assert view.tile_errors == {}
        assert issues == [("a.png", "No such file or directory")]

    def test_error_for_a_path_outside_the_folder_is_ignored(self, scheduled):
        view, toasts, issues = _toasting_view(["a.png"])
        tile_loader.on_thumbnail_error(view, "gone.png", "bad", 1)
        assert (toasts, issues, view.tile_errors) == ([], [], {})


class TestThumbnailLanding:
    def test_landing_clears_failure_state_and_records_signature(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(b"pixels")
        key = str(path)
        cleared: list = []
        view = _fake_view([key])
        view.grid_mutex = QMutex()
        view.main_window = SimpleNamespace(clear_image_issue=cleared.append)
        view.tile_errors[key] = "bad"
        view._tile_error_toasted.add(key)
        view.offline_paths.add(key)
        view._tile_retry_counts = {key: 1}
        view._tile_file_signatures = None
        view._filmstrip_pending.add(key)

        tile_loader.on_thumbnail_loaded(view, "img", key, 1)

        assert view.tile_cache == {key: "img"}
        assert (view.tile_errors, view._tile_error_toasted, view.offline_paths) == ({}, set(), set())
        assert view._tile_retry_counts == {}
        assert view._filmstrip_pending == set()
        assert cleared == [key]
        assert view._tile_file_signatures == {key: tile_loader.file_signature(key)}
        assert key in view._tile_load_times

    def test_landing_for_a_stale_generation_is_dropped(self):
        view = _fake_view(["a.png"], generation=2)
        tile_loader.on_thumbnail_loaded(view, "img", "a.png", 1)
        assert view.tile_cache == {}

    def test_add_thumbnail_rejects_stale_generation_but_accepts_none(self):
        view = _fake_view(["a.png"], generation=2)
        tile_loader.add_thumbnail(view, "old", "a.png", 1)
        assert view.tile_cache == {}
        tile_loader.add_thumbnail(view, "new", "a.png")
        assert view.tile_cache == {"a.png": "new"}

    def test_progress_forwards_the_counters(self):
        shown: list = []
        view = _fake_view([])
        view.main_window = SimpleNamespace(show_progress=lambda done, total: shown.append((done, total)))
        view._tile_load_count, view._tile_load_total = 3, 7
        tile_loader.flush_thumbnail_progress(view)
        assert shown == [(3, 7)]
        tile_loader.flush_thumbnail_progress(_fake_view([]))   # no show_progress: no-op


class TestIncrementalSync:
    def test_identical_list_is_a_noop(self):
        view = _fake_view(["a.png"])
        tile_loader.sync_tile_grid_incremental(view, ["a.png"])
        assert view._load_generation == 1
        assert _FakeWorker.created == []

    def test_focused_path_keeps_focus_at_its_new_index(self):
        view = _fake_view(["a.png", "b.png"], cache={"a.png": 1, "b.png": 2})
        view.focused_tile_index = 1
        view.selected_tiles = {"a.png", "b.png"}
        tile_loader.sync_tile_grid_incremental(view, ["c.png", "b.png"])
        assert view.focused_tile_index == 1
        assert view.selected_tiles == {"b.png"}
        assert view._load_generation == 2
        assert view.tile_grid_mode is True
        assert [w.path for w in _FakeWorker.created] == ["c.png"]

    def test_removed_focus_is_clamped_into_the_new_list(self):
        view = _fake_view(["a.png", "b.png", "c.png"])
        view.focused_tile_index = 2
        tile_loader.sync_tile_grid_incremental(view, ["x.png"])
        assert view.focused_tile_index == 0

    def test_empty_list_clears_focus(self):
        from Imervue.gpu_image_view.tile_focus import NO_FOCUS
        view = _fake_view(["a.png"], cache={"a.png": 1})
        tile_loader.sync_tile_grid_incremental(view, [])
        assert view.focused_tile_index == NO_FOCUS
        assert view.tile_cache == {}

    def test_dropped_paths_lose_every_per_path_record(self):
        view = _fake_view(["a.png", "b.png"], cache={"a.png": 1})
        view.tile_errors["a.png"] = "bad"
        view._filmstrip_thumb_cache["a.png"] = 1
        view._tile_load_times["a.png"] = 1.0
        view._tile_file_signatures["a.png"] = (1, 2, ".png")
        tile_loader.sync_tile_grid_incremental(view, ["b.png"])
        assert view.tile_errors == {}
        assert view._filmstrip_thumb_cache == {}
        assert view._tile_load_times == {}
        assert view._tile_file_signatures == {}

    def test_rename_migrates_the_file_signature(self, tmp_path):
        old = tmp_path / "old.png"
        old.write_bytes(b"bytes")
        sig = tile_loader.file_signature(str(old))
        view = _fake_view([str(old)], cache={str(old): 1})
        view._tile_file_signatures[str(old)] = sig
        old.replace(tmp_path / "new.png")
        tile_loader.sync_tile_grid_incremental(view, [str(tmp_path / "new.png")])
        assert view._tile_file_signatures == {str(tmp_path / "new.png"): sig}

    def test_two_identical_renames_pair_each_old_path_once(self, tmp_path):
        olds = [tmp_path / "a.png", tmp_path / "b.png"]
        for path in olds:
            path.write_bytes(b"same")
        view = _fake_view([str(p) for p in olds], cache={str(p): str(p) for p in olds})
        for path in olds:
            view._tile_file_signatures[str(path)] = tile_loader.file_signature(str(path))
        news = [tmp_path / "c.png", tmp_path / "d.png"]
        for old, new in zip(olds, news, strict=True):
            old.replace(new)
            new.touch()
            sig = tile_loader.file_signature(str(new))
            view._tile_file_signatures[str(old)] = sig
        tile_loader.sync_tile_grid_incremental(view, [str(p) for p in news])
        assert sorted(view.tile_cache) == sorted(str(p) for p in news)
        assert len(set(view.tile_cache.values())) == 2


class TestFolderSwitch:
    def test_load_resets_the_wall_and_reports_progress(self):
        progress: list = []
        view = _fake_view(["old.png"], cache={"old.png": 1})
        calls: list = []
        for name in ("_cancel_tile_workers", "_cancel_deep_zoom_worker",
                     "_cancel_all_prefetch", "_delete_all_tile_textures", "_clear_deep_zoom"):
            setattr(view, name, lambda _n=name: calls.append(_n))
        view._view_memory = {"old.png": 1}
        view._user_locked_view = True
        view.tile_errors["old.png"] = "bad"
        view._filmstrip_pending.add("old.png")

        def _refresh():
            raise RuntimeError("list view gone")

        view.main_window = SimpleNamespace(
            show_progress=lambda done, total: progress.append((done, total)),
            refresh_list_view=_refresh,
        )
        tile_loader.load_tile_grid_async(view, ["a.png", "b.png"])
        assert view._load_generation == 2
        assert view.model.images == ["a.png", "b.png"]
        assert (view.tile_cache, view.tile_errors, view._filmstrip_pending) == ({}, {}, set())
        assert (view._view_memory, view._user_locked_view) == ({}, False)
        assert view.tile_grid_mode is True
        assert progress[0] == (0, 2)
        assert calls == ["_cancel_tile_workers", "_cancel_deep_zoom_worker", "_cancel_all_prefetch",
                         "_delete_all_tile_textures", "_clear_deep_zoom"]
        assert sorted(w.path for w in _FakeWorker.created) == ["a.png", "b.png"]


class TestOfflineReporting:
    def test_newly_missing_and_recovered_paths_reach_the_issue_panel(self):
        recorded: list = []
        cleared: list = []
        refetched: list = []
        view = _fake_view(["gone.png", "back.png"])
        view.offline_paths = {"back.png"}
        view.main_window = SimpleNamespace(
            record_image_issue=lambda path, message: recorded.append((path, message)),
            clear_image_issue=cleared.append,
            refetch_list_rows=refetched.append,
        )
        view._offline_scan_inflight = True
        tile_loader.on_offline_scan_finished(view, {"gone.png"}, 1)
        assert recorded == [("gone.png", "File not found")]
        assert cleared == ["back.png"]
        assert refetched == [{"gone.png", "back.png"}]
        assert view.offline_paths == {"gone.png"}
        assert [w.path for w in _FakeWorker.created] == ["back.png"]

    def test_offline_scan_worker_reports_its_generation(self, tmp_path):
        present = tmp_path / "a.png"
        present.write_bytes(b"x")
        worker = tile_loader.OfflineScanWorker([str(present), str(tmp_path / "gone.png")], 5)
        results: list = []
        worker.signals.finished.connect(lambda *args: results.append(args))
        worker.run()
        assert results == [({str(tmp_path / "gone.png")}, 5, set())]


class TestWorkerWiring:
    def test_queue_worker_error_signal_is_wired(self, monkeypatch):
        class _ErrWorker(_FakeWorker):
            def __init__(self, path, size, generation):
                super().__init__(path, size, generation)
                self.signals.error = _FakeSignal()

        view = _fake_view(["a.png"])
        view._on_thumbnail_error = object()
        monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _ErrWorker)
        tile_loader.ensure_filmstrip_thumbnail(view, "a.png")
        worker = _FakeWorker.created[0]
        assert view._on_thumbnail_error in worker.signals.error.connected
        assert worker in view.active_tile_workers
        assert view.thumbnail_pool.started == [worker]
