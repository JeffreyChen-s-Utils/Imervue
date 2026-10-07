"""Latest-only jobs, bounded queues, CPU-thread isolation and owner lifetime."""
from __future__ import annotations

import threading

import pytest
from PIL import Image
from PySide6.QtCore import QThreadPool

from Imervue.gui import develop_preview as module
from Imervue.image.develop_preview import PreviewCancelledError
from Imervue.image.recipe import Recipe


@pytest.fixture
def scheduler(qapp, pump_until):
    controller = module.PreviewScheduler()
    yield controller
    controller.cancel()
    pump_until(lambda: controller.is_idle, timeout=5000)
    controller.deleteLater()


def test_jobs_run_off_ui_and_callbacks_run_on_ui(scheduler, pump_until, monkeypatch):
    ui_thread = threading.get_ident()
    worker_threads = []
    receiver_threads = []
    original = module.render_preview

    def render(*args, **kwargs):
        worker_threads.append(threading.get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "render_preview", render)
    scheduler.result_ready.connect(lambda result: receiver_threads.append(threading.get_ident()))
    scheduler.request("a", Image.new("RGBA", (32, 19)), Recipe(exposure=.2), final=True)
    pump_until(lambda: scheduler.is_idle)
    assert worker_threads and all(t != ui_thread for t in worker_threads)
    assert receiver_threads == [ui_thread]


def test_rapid_updates_keep_only_latest_pending_recipe(scheduler, pump_until, monkeypatch):
    started, release = threading.Event(), threading.Event()
    original = module.render_preview
    executed, results = [], []

    def render(request, *args, **kwargs):
        executed.append(request.recipe.exposure)
        if len(executed) == 1:
            started.set()
            if not release.wait(5):
                raise TimeoutError("test must release worker")
        return original(request, *args, **kwargs)

    monkeypatch.setattr(module, "render_preview", render)
    scheduler.result_ready.connect(results.append)
    source = Image.new("RGBA", (32, 19), (31, 47, 63, 255))
    try:
        scheduler.request("a", source, Recipe(exposure=.1), final=False)
        pump_until(started.is_set)
        for value in (.2, .3, .4, .5):
            scheduler.request("a", source, Recipe(exposure=value), final=True)
        assert scheduler._low is not None
        assert scheduler._pending.recipe.exposure == .5
        release.set()
        pump_until(lambda: scheduler.is_idle)
        assert executed == [.1, .5]
        assert [r.request.recipe.exposure for r in results] == [.5]
    finally:
        release.set()


def test_path_switch_discards_running_result_and_owns_recipe(scheduler, pump_until, monkeypatch):
    started, release = threading.Event(), threading.Event()
    original = module.render_preview
    results, produced = [], []

    def render(request, *args, **kwargs):
        if request.path == "a":
            started.set()
            if not release.wait(5):
                raise TimeoutError("test must release worker")
            # Force a real obsolete result through the worker's cancellation
            # guard: generation checks must independently reject it.
            request.cancelled.clear()
        output = original(request, *args, **kwargs)
        produced.append(request.path)
        return output

    monkeypatch.setattr(module, "render_preview", render)
    scheduler.result_ready.connect(results.append)
    recipe = Recipe(exposure=.2, extra={"future": {"value": 7}})
    try:
        scheduler.request("a", Image.new("RGBA", (32, 19)), Recipe(), final=False)
        pump_until(started.is_set)
        scheduler.request("b", Image.new("RGBA", (40, 27)), recipe, final=True)
        recipe.exposure = .9
        recipe.extra["future"]["value"] = 99
        release.set()
        pump_until(lambda: scheduler.is_idle)
        assert produced == ["a", "b"]
        assert len(results) == 1
        assert results[0].request.path == "b"
        assert results[0].request.recipe.exposure == .2
        assert results[0].request.recipe.extra["future"]["value"] == 7
    finally:
        release.set()


def test_large_drag_then_pause_emits_reduced_and_full_once(scheduler, pump_until):
    source = Image.new("RGBA", (1000, 800), (31, 47, 63, 255))
    recipe = Recipe(exposure=.2)
    results = []
    scheduler.result_ready.connect(results.append)
    scheduler.request("a", source, recipe, final=False)
    pump_until(lambda: scheduler.is_idle)
    assert [r.pixels.full_quality for r in results] == [False]
    version = scheduler.version
    scheduler.request("a", source, recipe, final=True)
    pump_until(lambda: scheduler.is_idle)
    scheduler.request("a", source, recipe, final=True)
    assert scheduler.version == version
    assert scheduler.is_idle
    assert [r.pixels.full_quality for r in results] == [False, True]
    assert results[-1].pixels.image.size == source.size


def test_full_failure_is_reported_once_without_retry_loop(scheduler, pump_until, monkeypatch):
    original = module.render_preview
    errors, attempts = [], []

    def render(request, cache, *, full):
        attempts.append(full)
        if full:
            raise MemoryError("not enough memory")
        return original(request, cache, full=full)

    monkeypatch.setattr(module, "render_preview", render)
    scheduler.failed.connect(errors.append)
    scheduler.request("a", Image.new("RGBA", (1000, 800)), Recipe(exposure=.2), final=True)
    pump_until(lambda: scheduler.is_idle)
    assert attempts == [False, True]
    assert errors == ["not enough memory"]


def test_reduced_failure_can_fall_back_to_canonical_pipeline(scheduler, pump_until, monkeypatch):
    original = module.render_preview
    results = []

    def render(request, cache, *, full):
        if not full:
            raise ValueError("approximation unavailable")
        return original(request, cache, full=full)

    monkeypatch.setattr(module, "render_preview", render)
    scheduler.result_ready.connect(results.append)
    scheduler.request("a", Image.new("RGBA", (1000, 800)), Recipe(), final=True)
    pump_until(lambda: scheduler.is_idle)
    assert len(results) == 1 and results[0].pixels.full_quality


def test_cancelled_jobs_drain_without_failure_or_result(scheduler, pump_until, monkeypatch):
    results, errors = [], []
    monkeypatch.setattr(module, "render_preview", lambda *a, **k: (_ for _ in ()).throw(
        PreviewCancelledError()))
    scheduler.result_ready.connect(results.append)
    scheduler.failed.connect(errors.append)
    scheduler.request("a", Image.new("RGBA", (32, 19)), Recipe(), final=False)
    pump_until(lambda: scheduler.is_idle)
    assert results == errors == []


def test_destroy_owner_during_running_job_is_safe(qapp, pump_until, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QWidget
    owner = QWidget()
    controller = module.PreviewScheduler(owner)
    started, release, completed = threading.Event(), threading.Event(), threading.Event()
    original = module.render_preview

    def render(request, *args, **kwargs):
        started.set()
        try:
            if not release.wait(5):
                raise TimeoutError("test must release worker")
            return original(request, *args, **kwargs)
        finally:
            completed.set()

    monkeypatch.setattr(module, "render_preview", render)
    try:
        controller.request("a", Image.new("RGBA", (32, 19)), Recipe(), final=False)
        pump_until(started.is_set)
        owner.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        release.set()
        pump_until(completed.is_set)
    finally:
        release.set()
        assert QThreadPool.globalInstance().waitForDone(5000)
