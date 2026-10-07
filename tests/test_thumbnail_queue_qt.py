"""Real pool completions reach the UI; cancellation never waits on blocked jobs."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, QMutex

from Imervue.gpu_image_view import tile_loader
from Imervue.gpu_image_view.gpu_image_view import GPUImageView
from Imervue.gpu_image_view.images.load_thumbnail_worker import WorkerSignals


class Host(QObject):
    def __init__(self):
        super().__init__()
        self.model = SimpleNamespace(images=[str(i) for i in range(1000)])
        self.thumbnail_size = 16
        self.tile_cache = {}
        self.tile_errors = {}
        self.offline_paths = set()
        self._filmstrip_pending = set()
        self._tile_load_times = {}
        self._tile_retry_counts = {}
        self._tile_max_dimensions = (0, 0)
        self.grid_mutex = QMutex()
        self._overlay = SimpleNamespace(ensure_fade_pump=lambda: None)
        self.main_window = SimpleNamespace()
        self._progress_coalescer = SimpleNamespace(schedule=lambda: None, force_flush=lambda: None)
        self._load_generation = 1
        self.active_tile_workers = set()
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(2)
        self.tile_grid_mode = True
        self.grid_offset_y = 0
        self.thread_checks = []

    def width(self):
        return 64

    def height(self):
        return 32

    def update(self):
        pass

    def _on_thumbnail_loaded(self, data, path, generation):
        self.thread_checks.append(QThread.currentThread() == self.thread())
        tile_loader.on_thumbnail_loaded(self, data, path, generation)

    def _on_thumbnail_error(self, path, message, generation):
        tile_loader.on_thumbnail_error(self, path, message, generation)


def _worker_type(release, entered):
    class Worker(QRunnable):
        def __init__(self, path, size, generation):
            super().__init__()
            self.path, self.generation = path, generation
            self.signals = WorkerSignals()
            self._abort = False

        def abort(self):
            self._abort = True

        def run(self):
            entered.append(threading.get_ident())
            if release.wait(10) and not self._abort:
                self.signals.finished.emit(np.ones((16, 16, 4), dtype=np.uint8),
                                           self.path, self.generation)

    return Worker


def _dispose(host, release):
    GPUImageView._cancel_tile_workers(host)
    host._load_generation += 1
    release.set()
    assert host.thumbnail_pool.waitForDone(10_000)
    host.deleteLater()


def test_real_pool_drains_current_viewport_on_ui_thread(qapp, monkeypatch, pump_until):
    host = Host()
    release, entered = threading.Event(), []
    monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _worker_type(release, entered))
    try:
        tile_loader._spawn_thumbnail_workers(host, host.model.images, 1)
        assert pump_until(lambda: len(entered) == 2)
        assert len(host.active_tile_workers) == 2
        assert all(t != threading.get_ident() for t in entered)
        host.grid_offset_y = -1600
        tile_loader.pump_thumbnail_workers(host)
        release.set()
        assert pump_until(lambda: not host.active_tile_workers)
        assert host.thread_checks and all(host.thread_checks)
        assert len(host.tile_cache) < 30
        assert host._tile_load_count == host._tile_load_total
        assert all(int(path) >= 390 for path in host._tile_queue.requested)
    finally:
        _dispose(host, release)


def test_cancel_blocked_jobs_does_not_wait_or_restart_queue(qapp, monkeypatch, pump_until):
    host = Host()
    release, entered = threading.Event(), []
    monkeypatch.setattr(tile_loader, "LoadThumbnailWorker", _worker_type(release, entered))
    real_wait = host.thumbnail_pool.waitForDone
    try:
        tile_loader._spawn_thumbnail_workers(host, host.model.images, 1)
        assert pump_until(lambda: len(entered) == 2)

        def forbidden(*args):
            raise AssertionError("UI cancellation waited on a worker")

        monkeypatch.setattr(host.thumbnail_pool, "waitForDone", forbidden)
        GPUImageView._cancel_tile_workers(host)
        assert host._tile_queue is None
        assert not host.active_tile_workers
        assert not release.is_set()
        assert host.thumbnail_pool.activeThreadCount() == 2
        release.set()
        assert real_wait(10_000)
        assert not host.tile_cache
    finally:
        monkeypatch.setattr(host.thumbnail_pool, "waitForDone", real_wait)
        _dispose(host, release)
