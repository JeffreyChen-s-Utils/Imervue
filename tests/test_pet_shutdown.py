"""Tests for stopping a desktop pet's background workers on despawn.

despawn used to only hide + deleteLater the window, so the webcam stayed open
(camera LED lit), the webhook port stayed bound, and the global hotkey OS hook
stayed installed — the spawned threads / hooks outlived the C++ QObject. Each
layer now exposes a non-persisting ``shutdown``; despawn calls the window's.

Every test drives the methods unbound on light fakes — no window is constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.desktop_pet.pet_canvas_drivers import PetCanvasDrivers
from Imervue.desktop_pet.pet_drivers import CanvasDriverController
from Imervue.desktop_pet.pet_feature_base import IntegrationController
from Imervue.desktop_pet.pet_registry import PetRegistry
from Imervue.desktop_pet.pet_window import PetWindow


def test_integration_shutdown_stops_client_without_persisting():
    stopped: list = []
    persisted: list = []
    fake = SimpleNamespace(
        _client=SimpleNamespace(stop=lambda: stopped.append(True)),
        _host=SimpleNamespace(persist=lambda **k: persisted.append(k)),
    )
    IntegrationController.shutdown(fake)
    assert stopped == [True]
    assert persisted == []          # despawn must not persist "disabled"


def test_integration_shutdown_is_a_noop_without_a_client():
    IntegrationController.shutdown(SimpleNamespace(_client=None))  # no raise


def test_canvas_driver_shutdown_disables_without_persisting():
    calls: list = []
    fake = SimpleNamespace(
        _driver=SimpleNamespace(set_enabled=calls.append),
        _host=SimpleNamespace(persist_driver=lambda *a: calls.append("persist")),
    )
    CanvasDriverController.shutdown(fake)
    assert calls == [False]         # disabled, no persist_driver


def test_canvas_drivers_shutdown_disables_each_optional_driver():
    disabled: list = []

    def _driver(name):
        return SimpleNamespace(set_enabled=lambda v, n=name: disabled.append((n, v)))

    fake = SimpleNamespace(
        webcam_tracker=_driver("webcam"),
        virtual_camera=_driver("vcam"),
        idle_driver=_driver("idle"),
        idle_cycler=None,            # not built — must be skipped, not crash
        mouse_gaze=_driver("gaze"),
    )
    PetCanvasDrivers.shutdown(fake)
    assert {n for n, _ in disabled} == {"webcam", "vcam", "idle", "gaze"}
    assert all(v is False for _, v in disabled)


def test_pet_window_shutdown_stops_features_music_and_canvas_drivers():
    calls: list = []
    fake = SimpleNamespace(
        _features={
            "webhook": SimpleNamespace(shutdown=lambda: calls.append("webhook")),
            "hotkeys": SimpleNamespace(shutdown=lambda: calls.append("hotkeys")),
        },
        _music_rhythm=SimpleNamespace(shutdown=lambda: calls.append("music")),
        _canvas_drivers=SimpleNamespace(shutdown=lambda: calls.append("drivers")),
        _llm=SimpleNamespace(shutdown=lambda: calls.append("llm")),
    )
    PetWindow.shutdown(fake)
    assert set(calls) == {"webhook", "hotkeys", "music", "drivers", "llm"}


def test_pet_window_shutdown_logs_a_failing_step_and_carries_on(caplog):
    calls: list = []

    def broken():
        raise RuntimeError("port already closed")

    fake = SimpleNamespace(
        _features={"webhook": SimpleNamespace(shutdown=broken),
                   "hotkeys": SimpleNamespace(shutdown=lambda: calls.append("hotkeys"))},
        _music_rhythm=SimpleNamespace(shutdown=lambda: calls.append("music")),
        _canvas_drivers=SimpleNamespace(shutdown=lambda: calls.append("drivers")),
        _llm=SimpleNamespace(shutdown=lambda: calls.append("llm")),
    )
    with caplog.at_level("DEBUG", logger="Imervue"):
        PetWindow.shutdown(fake)
    assert calls == ["hotkeys", "music", "drivers", "llm"]
    (record,) = [r for r in caplog.records if r.exc_info]
    assert "shut down a feature controller" in record.getMessage()
    assert record.exc_info[0] is RuntimeError


def test_integration_shutdown_logs_a_failing_stop(caplog):
    def broken():
        raise OSError("socket gone")

    fake = SimpleNamespace(_client=SimpleNamespace(stop=broken))
    with caplog.at_level("DEBUG", logger="Imervue"):
        IntegrationController.shutdown(fake)
    assert [r.getMessage() for r in caplog.records] == [
        "Best-effort step failed: stop the integration client"]


def test_despawn_shuts_the_window_down_before_deleting():
    events: list = []
    window = SimpleNamespace(
        shutdown=lambda: events.append("shutdown"),
        hide=lambda: events.append("hide"),
        deleteLater=lambda: events.append("delete"),
    )
    fake_reg = SimpleNamespace(
        _pets={"x": window},
        pet_despawned=SimpleNamespace(emit=lambda pid: events.append(("emit", pid))),
    )
    assert PetRegistry.despawn(fake_reg, "x") is True
    # Full sequence: workers stopped first, then hide, delete, and the signal —
    # a whole-list equality (no subscripting) so the ordering is exact.
    assert events == ["shutdown", "hide", "delete", ("emit", "x")]
