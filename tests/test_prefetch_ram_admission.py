"""Real worker admission retains blocked decoders until their terminal callback."""
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
from shiboken6 import isValid
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, QThreadPool, Qt

from Imervue.gpu_image_view.images import image_loader
from Imervue.gpu_image_view.prefetch_scheduler import PrefetchScheduler
from Imervue.gpu_image_view.ram_budget import RamBudget


class _View(QObject):
    def __init__(self):
        super().__init__()
        self.model = SimpleNamespace(images=["a.png", "b.png", "c.png"])
        self.current_index = 0
        self._hover_tile_path = None
        self.deep_zoom = None
        self.prefetch_pool = QThreadPool()
        self.prefetch_pool.setMaxThreadCount(2)
        self._prefetch = PrefetchScheduler(self)
        self._prefetch.budget = RamBudget(100)
        self.errors = []
        self.callback_threads = []

    def _on_prefetch_loaded(self, dzi, path):
        self.callback_threads.append(QThread.currentThread())
        self._prefetch.pop_worker(path)
        self._prefetch.store(path, dzi)

    def _on_prefetch_error(self, path, message):
        self.errors.append((path, message))
        self._prefetch.pop_worker(path)


def test_cancelled_blocked_decode_keeps_reservation(qapp, pump_until, monkeypatch):
    from Imervue.gpu_image_view import ram_budget
    entered, release = Event(), Event()
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: 60)

    def blocked(*_args, **_kwargs):
        entered.set()
        if not release.wait(10):
            raise TimeoutError("test decoder was not released")
        return np.zeros((2, 2, 4), dtype=np.uint8)

    monkeypatch.setattr(image_loader, "load_image_file", blocked)
    view = _View()
    try:
        view._prefetch.schedule()
        assert pump_until(entered.is_set)
        assert pump_until(lambda: len(view._prefetch.workers) == 1)
        assert view._prefetch.budget.used_bytes == 60
        view._prefetch.cancel_all()
        assert not view._prefetch.workers
        assert view._prefetch.budget.used_bytes == 60
        view._prefetch.schedule()
        assert not view._prefetch.budget.reserve("extra", 41)
        assert pump_until(lambda: not view._prefetch.workers)
        assert not view._prefetch.workers
        release.set()
        assert pump_until(lambda: view.prefetch_pool.activeThreadCount() == 0)
        assert pump_until(lambda: view._prefetch.budget.used_bytes == 0)
        assert not view._prefetch.cache
    finally:
        view._prefetch.cancel_all()
        release.set()
        view.prefetch_pool.waitForDone(10000)
        view.deleteLater()


def test_queued_result_transfers_actual_pyramid_bytes(qapp, pump_until, monkeypatch):
    from Imervue.gpu_image_view import ram_budget
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: 40)
    monkeypatch.setattr(image_loader, "load_image_file",
                        lambda *_args, **_kwargs: np.zeros((2, 2, 4), dtype=np.uint8))
    view = _View()
    try:
        view._prefetch.schedule()
        assert pump_until(lambda: len(view._prefetch.cache) == 2)
        assert view._prefetch.budget.used_bytes == 32
        assert view.callback_threads == [view.thread(), view.thread()]
        assert not view._prefetch.budget.reservations
        view._prefetch.take("b.png")
        assert view._prefetch.budget.used_bytes == 16
        view._prefetch.discard("c.png")
        assert view._prefetch.budget.used_bytes == 0
    finally:
        view._prefetch.cancel_all()
        view.prefetch_pool.waitForDone(10000)
        view.deleteLater()


def test_decode_failure_releases_ticket_and_is_reported_on_ui(qapp, pump_until, monkeypatch):
    from Imervue.gpu_image_view import ram_budget
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: 40)

    def damaged(*_args, **_kwargs):
        raise OSError("damaged camera file")

    monkeypatch.setattr(image_loader, "load_image_file", damaged)
    view = _View()
    try:
        view._prefetch.schedule()
        assert pump_until(lambda: not view._prefetch.workers)
        assert sorted(view.errors) == [
            ("b.png", "damaged camera file"), ("c.png", "damaged camera file"),
        ]
        assert view._prefetch.budget.used_bytes == 0
        assert not view._prefetch.cache
    finally:
        view._prefetch.cancel_all()
        view.prefetch_pool.waitForDone(10000)
        view.deleteLater()


@pytest.mark.parametrize("abort,estimate,shape", [
    (True, 40, (2, 2, 4)), (False, 101, (2, 2, 4)), (False, 40, (6, 6, 4)),
])
def test_worker_terminal_signal_covers_abort_refusal_and_underestimated_result(
    qapp, monkeypatch, abort, estimate, shape,
):
    from Imervue.gpu_image_view import ram_budget
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: estimate)
    decoded, completed = [], []

    def decode(*_args, **_kwargs):
        decoded.append(True)
        return np.zeros(shape, dtype=np.uint8)

    monkeypatch.setattr(image_loader, "load_image_file", decode)
    budget = RamBudget(100)
    worker = image_loader.LoadDeepZoomWorker("a.png", memory_budget=budget)
    worker.signals.completed.connect(lambda *args: completed.append(args),
                                     Qt.ConnectionType.DirectConnection)
    if abort:
        worker.abort()
    worker.run()
    assert completed == [(worker, None, "")]
    assert bool(decoded) == (not abort and estimate <= 100)
    assert budget.used_bytes == 0


def test_old_same_path_completion_cannot_remove_replacement_worker(qapp):
    view = _View()
    try:
        old = image_loader.LoadDeepZoomWorker("b.png", memory_budget=view._prefetch.budget)
        new = image_loader.LoadDeepZoomWorker("b.png", memory_budget=view._prefetch.budget)
        view._prefetch.workers["b.png"] = new
        view._prefetch._retired.add(old)
        assert view._prefetch.budget.reserve(old, 40)
        assert view._prefetch.budget.reserve(new, 40)
        view._prefetch._on_completed(old, np.zeros((2, 2, 4), dtype=np.uint8), "")
        assert view._prefetch.workers["b.png"] is new
        assert not view._prefetch.cache
        assert view._prefetch.budget.used_bytes == 40
        assert old not in view._prefetch._retired
        view._prefetch._on_completed(new, np.zeros((2, 2, 4), dtype=np.uint8), "")
        assert not view._prefetch.workers
        assert view._prefetch.budget.used_bytes == 16
    finally:
        view._prefetch.cancel_all()
        view.deleteLater()


def test_refused_promoted_prefetch_starts_foreground_load(qapp, pump_until, monkeypatch):
    from Imervue.gpu_image_view import ram_budget
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: 101)
    started = []
    view = _View()
    view._deep_zoom_loading = "b.png"
    view._deep_zoom_request_id = 7
    view._start_deep_zoom_worker = lambda *args: started.append(args)
    try:
        view._prefetch.schedule()
        assert pump_until(lambda: not view._prefetch.workers)
        assert started == [("b.png", 7)]
        assert view._prefetch.budget.used_bytes == 0
        assert not view.errors
    finally:
        view._prefetch.cancel_all()
        view.prefetch_pool.waitForDone(10000)
        view.deleteLater()


def test_destroyed_owner_releases_result_queued_before_ui_delivery(qapp, monkeypatch):
    from Imervue.gpu_image_view import ram_budget
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: 40)
    monkeypatch.setattr(image_loader, "load_image_file",
                        lambda *_args, **_kwargs: np.zeros((2, 2, 4), dtype=np.uint8))
    view = _View()
    budget = view._prefetch.budget
    try:
        view._prefetch.schedule()
        assert view.prefetch_pool.waitForDone(10000)
        assert budget.used_bytes == 32
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert budget.used_bytes == 0
    finally:
        view.prefetch_pool.waitForDone(10000)
        if isValid(view):
            view.deleteLater()


def test_destroyed_owner_keeps_running_decode_reserved(qapp, pump_until, monkeypatch):
    from Imervue.gpu_image_view import ram_budget
    entered, release = Event(), Event()
    monkeypatch.setattr(ram_budget, "decode_reservation", lambda *_args: 60)

    def blocked(*_args, **_kwargs):
        entered.set()
        if not release.wait(10):
            raise TimeoutError("test decoder was not released")
        return np.zeros((2, 2, 4), dtype=np.uint8)

    monkeypatch.setattr(image_loader, "load_image_file", blocked)
    view = _View()
    budget, pool = view._prefetch.budget, view.prefetch_pool
    try:
        view._prefetch.schedule()
        assert pump_until(entered.is_set)
        assert pump_until(lambda: len(view._prefetch.workers) == 1)
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert budget.used_bytes == 60
        release.set()
        assert pump_until(lambda: budget.used_bytes == 0)
    finally:
        release.set()
        pool.waitForDone(10000)
        if isValid(view):
            view._prefetch.cancel_all()
            view.deleteLater()
