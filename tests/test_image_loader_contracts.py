"""Contracts of ``image_loader``: its import surface, worker signalling and open-path state order."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view import ram_budget
from Imervue.gpu_image_view.images import image_loader
from Imervue.user_settings.user_setting_dict import user_setting_dict

_PUBLIC_NAMES = (
    "open_path", "decode_image_file", "decode_image", "load_image_file", "_load_raw",
    "_load_raster", "_load_raster_thumbnail", "_load_svg", "_ensure_rgba", "decode_slot",
    "_scan_images", "_scan_images_for_user", "_sort_for_user", "_is_listed",
    "LoadDeepZoomWorker", "FolderScanWorker", "cancel_folder_scan", "_open_folder",
    "_open_file", "_on_folder_scan_batch", "_on_folder_scan_finished", "_maybe_hint_heif",
    "_maybe_collapse_stacks", "_apply_folder_scan_paths", "_locate_current_index",
)


@pytest.mark.parametrize("name", _PUBLIC_NAMES)
def test_every_name_callers_use_is_importable_from_the_loader(name):
    assert hasattr(image_loader, name)


# ---------------------------------------------------------------- LoadDeepZoomWorker

class _Budget:
    def __init__(self, *, grant=True):
        self.grant = grant
        self.reserved: list[int] = []
        self.released = 0

    def reserve(self, _owner, amount):
        self.reserved.append(amount)
        return self.grant

    def release(self, _owner):
        self.released += 1


def _record(worker):
    log = []
    worker.signals.finished.connect(lambda dzi, path: log.append(("finished", path)))
    worker.signals.error.connect(lambda path, msg: log.append(("error", path, msg)))
    worker.signals.completed.connect(
        lambda w, result, msg: log.append(("completed", result is not None, msg)))
    return log


def test_worker_decodes_through_the_patchable_loader_name(qapp, monkeypatch):
    calls = []

    def fake_load(path, thumbnail, recipe):
        calls.append((path, thumbnail, recipe))
        return np.zeros((4, 4, 4), dtype=np.uint8)

    monkeypatch.setattr(image_loader, "load_image_file", fake_load)
    worker = image_loader.LoadDeepZoomWorker("a.png", recipe="r", preview=True)
    log = _record(worker)
    worker.run()
    assert calls == [("a.png", True, "r")]
    assert log == [("finished", "a.png"), ("completed", True, "")]
    assert worker.completed.is_set()


def test_aborted_worker_never_decodes_and_completes_empty(qapp, monkeypatch):
    monkeypatch.setattr(image_loader, "load_image_file", lambda *a, **k: pytest.fail("decoded"))
    worker = image_loader.LoadDeepZoomWorker("a.png")
    log = _record(worker)
    worker.abort()
    worker.run()
    assert log == [("completed", False, "")]


def test_failed_decode_reports_the_error_then_completes(qapp, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("broken file")

    monkeypatch.setattr(image_loader, "load_image_file", boom)
    worker = image_loader.LoadDeepZoomWorker("a.png")
    log = _record(worker)
    worker.run()
    assert log == [("error", "a.png", "broken file"), ("completed", False, "broken file")]


def test_budgeted_worker_hands_its_result_only_through_completed(qapp, monkeypatch):
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda path, recipe: 7)
    monkeypatch.setattr(image_loader, "load_image_file",
                        lambda *a, **k: np.zeros((4, 4, 4), dtype=np.uint8))
    budget = _Budget()
    worker = image_loader.LoadDeepZoomWorker("a.png", memory_budget=budget)
    log = _record(worker)
    worker.run()
    assert log == [("completed", True, "")]
    assert budget.reserved[0] == 7 and len(budget.reserved) == 2
    assert budget.released == 0


def test_budget_refusal_skips_the_decode_and_releases(qapp, monkeypatch):
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda path, recipe: 7)
    monkeypatch.setattr(image_loader, "load_image_file", lambda *a, **k: pytest.fail("decoded"))
    budget = _Budget(grant=False)
    worker = image_loader.LoadDeepZoomWorker("a.png", memory_budget=budget)
    log = _record(worker)
    worker.run()
    assert log == [("completed", False, "")]
    assert budget.released == 1


# ---------------------------------------------------------------- FolderScanWorker

def test_folder_scan_batches_at_least_thirty_two_paths(qapp, tmp_path):
    for i in range(40):
        (tmp_path / f"{i}.png").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    worker = image_loader.FolderScanWorker(str(tmp_path), batch_size=1)
    assert worker.batch_size == 32
    batches, finished = [], []
    worker.signals.batch.connect(lambda _f, batch: batches.append(len(batch)))
    worker.signals.finished.connect(lambda _f, images: finished.append(images))
    worker.run()
    assert batches == [32, 8]
    assert len(finished) == 1 and len(finished[0]) == 40


def test_folder_scan_of_a_missing_folder_finishes_empty(qapp, tmp_path):
    worker = image_loader.FolderScanWorker(str(tmp_path / "gone"))
    finished = []
    worker.signals.finished.connect(lambda folder, images: finished.append((folder, images)))
    worker.run()
    assert finished == [(str(tmp_path / "gone"), [])]


def test_aborted_folder_scan_emits_nothing(qapp, tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    worker = image_loader.FolderScanWorker(str(tmp_path))
    emitted = []
    worker.signals.batch.connect(lambda *a: emitted.append("batch"))
    worker.signals.finished.connect(lambda *a: emitted.append("finished"))
    worker.abort()
    worker.run()
    assert emitted == []


# ---------------------------------------------------------------- sorting helpers

def test_sort_for_user_follows_the_name_setting(monkeypatch):
    monkeypatch.setitem(user_setting_dict, "sort_by", "name")
    monkeypatch.setitem(user_setting_dict, "sort_ascending", False)
    paths = [os.path.join("d", n) for n in ("img2.png", "img10.png", "img1.png")]
    assert [os.path.basename(p) for p in image_loader._sort_for_user(paths)] == [
        "img10.png", "img2.png", "img1.png"]


def test_scan_sorted_by_size_orders_by_the_listing(tmp_path):
    (tmp_path / "big.png").write_bytes(b"x" * 50)
    (tmp_path / "small.png").write_bytes(b"x")
    result = image_loader._scan_images(str(tmp_path), sort_by="size", ascending=True)
    assert [os.path.basename(p) for p in result] == ["small.png", "big.png"]


def test_locate_current_index_matches_exact_then_normalised_paths():
    images = ["a/x.png", os.path.normpath("b/y.png")]
    assert image_loader._locate_current_index(images, "a/x.png") == 0
    assert image_loader._locate_current_index(images, "b/./y.png") == 1
    assert image_loader._locate_current_index(images, "c/z.png") == 0


# ---------------------------------------------------------------- open_path dispatch

def test_open_path_dispatches_folders_and_viewer_files(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(image_loader, "_open_folder", lambda gui, p: calls.append(("folder", p)))
    monkeypatch.setattr(image_loader, "_open_file", lambda gui, p: calls.append(("file", p)))
    (tmp_path / "a.PNG").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    image_loader.open_path(None, str(tmp_path))
    image_loader.open_path(None, str(tmp_path / "a.PNG"))
    image_loader.open_path(None, str(tmp_path / "notes.txt"))
    image_loader.open_path(None, str(tmp_path / "missing.png"))
    assert calls == [("folder", tmp_path), ("file", tmp_path / "a.PNG")]


class _RecordingModel:
    def __init__(self, log):
        self._log = log
        self.images = []

    def set_images(self, images):
        self._log.append(("set_images", [os.path.basename(p) for p in images]))
        self.images = list(images)


def test_open_file_sets_viewer_state_in_order(tmp_path):
    for name in ("a.png", "b.png"):
        (tmp_path / name).write_bytes(b"x")
    log = []

    class _Viewer:
        def __setattr__(self, key, value):
            if key in ("current_index", "tile_grid_mode", "_unfiltered_images"):
                log.append((key, value if key != "_unfiltered_images" else len(value)))
            object.__setattr__(self, key, value)

    viewer = _Viewer()
    viewer.model = _RecordingModel(log)
    viewer.load_deep_zoom_image = lambda path: log.append(("load", os.path.basename(path)))
    viewer.main_window = SimpleNamespace(
        _reapply_filter_preserving_current=lambda: log.append(("reapply",)))
    log.clear()
    image_loader._open_file(viewer, tmp_path / "b.png")
    assert log == [
        ("_unfiltered_images", 2), ("set_images", ["a.png", "b.png"]), ("current_index", 1),
        ("tile_grid_mode", False), ("load", "b.png"), ("reapply",),
    ]
    assert viewer._folder_scan_active is False
    assert user_setting_dict["user_last_folder"] == str(tmp_path)
    assert user_setting_dict["user_recent_images"][0] == str(tmp_path / "b.png")


def test_cancel_folder_scan_survives_a_failing_abort(qapp):
    class _Worker:
        def abort(self):
            raise RuntimeError("already gone")

    view = SimpleNamespace(_folder_scan_worker=_Worker())
    image_loader.cancel_folder_scan(view)
    assert view._folder_scan_generation == 1
    assert view._folder_scan_worker is None
    assert view._folder_scan_updates is None
    assert view._folder_scan_active is False


def test_open_folder_scans_progressively_to_the_plugins(qapp, tmp_path, pump_until):
    for name in ("b.png", "a.png"):
        (tmp_path / name).write_bytes(b"x")
    loaded, dispatched = [], []
    manager = SimpleNamespace(
        dispatch_folder_opened=lambda folder, images, gui: dispatched.append((folder, images)))
    view = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=5,
                           main_window=SimpleNamespace(plugin_manager=manager))
    view.load_tile_grid_async = lambda paths: loaded.append((list(paths), view._folder_scan_active))
    image_loader._open_folder(view, Path(str(tmp_path)))
    assert loaded[0] == ([], True) and view.current_index == 0
    assert pump_until(lambda: dispatched)
    names = [os.path.basename(p) for p in dispatched[0][1]]
    assert dispatched[0][0] == str(tmp_path) and names == ["a.png", "b.png"]
    assert [os.path.basename(p) for p in loaded[-1][0]] == ["a.png", "b.png"]
    assert view._folder_scan_active is False and view._folder_scan_worker is None
    assert user_setting_dict["user_last_folder"] == str(tmp_path)


def test_folder_scan_paths_go_to_the_window_refresh_when_it_has_one(monkeypatch):
    monkeypatch.setitem(user_setting_dict, "stack_raw_jpeg_pairs", False)
    refreshed = []
    view = SimpleNamespace(
        main_window=SimpleNamespace(_apply_refreshed_image_list=refreshed.append),
        load_tile_grid_async=lambda _p: pytest.fail("grid loaded directly"))
    image_loader._apply_folder_scan_paths(view, ["a.png"])
    assert refreshed == [["a.png"]] and view._unfiltered_images == ["a.png"]
    assert view._stack_members == {}


def test_stale_scan_batches_are_ignored():
    view = SimpleNamespace(_folder_scan_generation=2,
                           _folder_scan_updates=SimpleNamespace(add=lambda b: pytest.fail("add")))
    image_loader._on_folder_scan_batch(view, "f", ["a.png"], 1)
    image_loader._on_folder_scan_finished(view, "f", ["a.png"], 1)
