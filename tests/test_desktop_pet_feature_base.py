"""Unit tests for the desktop-pet feature-controller scaffolding.

These exercise the pure lifecycle / merge logic extracted from
:class:`PetWindow` without instantiating any Qt widget — the
:class:`IntegrationController` only needs a fake host and a fake
worker, so the tests are cheap and deterministic.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.pet_feature_base import (
    IntegrationController,
    merge_bindings,
    sanitize_app_ids,
)


class _FakeHost:
    """Records every ``persist`` call and serves canned settings."""

    def __init__(self, settings: dict | None = None) -> None:
        self.persisted: dict = {}
        self._settings = settings or {}

    def persist(self, **fields: object) -> None:
        self.persisted.update(fields)

    def setting(self, key: str, default: object) -> object:
        return self._settings.get(key, default)


class _FakeWorker:
    """Minimal ``start`` / ``stop`` / ``is_running`` worker."""

    def __init__(self, *, start_ok: bool = True) -> None:
        self._start_ok = start_ok
        self._running = False
        self.starts = 0
        self.stops = 0
        self.configured = 0

    def start(self) -> bool:
        self.starts += 1
        self._running = self._start_ok
        return self._start_ok

    def stop(self) -> None:
        self.stops += 1
        self._running = False

    def is_running(self) -> bool:
        return self._running


class _StubController(IntegrationController):
    persist_key = "stub_enabled"

    def __init__(self, host, worker) -> None:
        super().__init__(host)
        self._worker = worker

    def _build_client(self):
        return self._worker

    def _configure(self, client) -> None:
        client.configured += 1


# ---------------------------------------------------------------
# merge_bindings
# ---------------------------------------------------------------


def test_merge_bindings_overlays_overrides():
    defaults = {"a": "ctrl+1", "b": "ctrl+2"}
    merged = merge_bindings(defaults, {"a": "alt+9"})
    assert merged == {"a": "alt+9", "b": "ctrl+2"}
    # Original defaults dict is not mutated.
    assert defaults["a"] == "ctrl+1"


def test_merge_bindings_ignores_non_string_and_empty_specs():
    defaults = {"a": "ctrl+1"}
    merged = merge_bindings(defaults, {"a": "", "b": 5, "c": None})
    assert merged == {"a": "ctrl+1"}


def test_merge_bindings_ignores_non_dict_persisted():
    defaults = {"a": "ctrl+1"}
    assert merge_bindings(defaults, None) == defaults
    assert merge_bindings(defaults, ["not", "a", "dict"]) == defaults


# ---------------------------------------------------------------
# sanitize_app_ids
# ---------------------------------------------------------------


def test_sanitize_app_ids_keeps_only_nonempty_strings():
    assert sanitize_app_ids(["a", "", "b", 3, None, "c"]) == ("a", "b", "c")


def test_sanitize_app_ids_rejects_non_list():
    assert sanitize_app_ids("a,b,c") == ()
    assert sanitize_app_ids(None) == ()
    assert sanitize_app_ids({"a": 1}) == ()


def test_sanitize_app_ids_empty_list():
    assert sanitize_app_ids([]) == ()


# ---------------------------------------------------------------
# IntegrationController lifecycle
# ---------------------------------------------------------------


def test_controller_enable_builds_configures_starts_and_persists_ok():
    host = _FakeHost()
    worker = _FakeWorker(start_ok=True)
    ctl = _StubController(host, worker)

    assert ctl.set_enabled(True) is True
    assert worker.configured == 1
    assert worker.starts == 1
    assert host.persisted == {"stub_enabled": True}
    assert ctl.is_enabled() is True


def test_controller_enable_failure_persists_false():
    host = _FakeHost()
    worker = _FakeWorker(start_ok=False)
    ctl = _StubController(host, worker)

    assert ctl.set_enabled(True) is False
    assert host.persisted == {"stub_enabled": False}
    # A failed start leaves the worker not running.
    assert ctl.is_enabled() is False


def test_controller_disable_stops_and_persists_false():
    host = _FakeHost()
    worker = _FakeWorker(start_ok=True)
    ctl = _StubController(host, worker)
    ctl.set_enabled(True)

    assert ctl.set_enabled(False) is True
    assert worker.stops == 1
    assert host.persisted == {"stub_enabled": False}
    assert ctl.is_enabled() is False


def test_controller_disable_without_client_is_safe():
    """Disabling a never-enabled controller must not build a worker."""
    host = _FakeHost()
    ctl = _StubController(host, _FakeWorker())
    assert ctl.set_enabled(False) is True
    assert host.persisted == {"stub_enabled": False}
    assert ctl.is_enabled() is False


def test_controller_reconfigures_each_enable():
    """A settings edit between enables must re-push config — the
    worker is built once but reconfigured every start."""
    host = _FakeHost()
    worker = _FakeWorker(start_ok=True)
    ctl = _StubController(host, worker)
    ctl.set_enabled(True)
    ctl.set_enabled(False)
    ctl.set_enabled(True)
    assert worker.configured == 2
    assert worker.starts == 2


def test_base_controller_build_client_not_implemented():
    """The base refuses to enable without a concrete _build_client."""
    ctl = IntegrationController(_FakeHost())
    ctl.persist_key = "x"
    with pytest.raises(NotImplementedError):
        ctl.set_enabled(True)
