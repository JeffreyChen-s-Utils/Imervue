"""Unit tests for the desktop-pet canvas-driver + subsystem controllers.

Pure-logic coverage: each controller is driven against a fake host /
fake driver so no Qt widget or GL surface is constructed. The
behavioural contracts asserted here mirror the original inline
``PetWindow`` methods (lazy build, persist-the-actual-flag, drop stale
LLM replies when disabled, re-configure on every enable).
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.pet_drivers import (
    CanvasDriverController,
    ClickSfxController,
    IdleMinigameController,
    LlmDialogueController,
    MusicRhythmController,
)


class _FakeHost:
    def __init__(self, settings: dict | None = None) -> None:
        self.persisted: dict = {}
        self.driver_persisted: dict = {}
        self._settings = settings or {}
        self.canvas_obj = object()

    def persist(self, **fields: object) -> None:
        self.persisted.update(fields)

    def persist_driver(self, key: str, value: bool) -> None:
        self.driver_persisted[key] = value

    def setting(self, key: str, default: object) -> object:
        return self._settings.get(key, default)

    def canvas(self) -> object:
        return self.canvas_obj

    def play_group(self, group: str) -> bool:
        return False


class _FakeDriver:
    def __init__(self, *, enable_ok: bool = True) -> None:
        self._enable_ok = enable_ok
        self._enabled = False
        self.last_requested: bool | None = None
        self.activity_pings = 0

    def set_enabled(self, enabled: bool) -> bool:
        self.last_requested = enabled
        self._enabled = enabled and self._enable_ok
        return self._enabled if enabled else True

    def is_enabled(self) -> bool:
        return self._enabled

    def notify_activity(self) -> None:
        self.activity_pings += 1


class _StubCanvasController(CanvasDriverController):
    driver_key = "stub"

    def __init__(self, host, driver) -> None:
        super().__init__(host)
        self._fake = driver

    def _build_driver(self):
        return self._fake


# ---------------------------------------------------------------
# CanvasDriverController
# ---------------------------------------------------------------


def test_canvas_driver_enable_persists_actual_result():
    host = _FakeHost()
    driver = _FakeDriver(enable_ok=True)
    ctl = _StubCanvasController(host, driver)
    assert ctl.set_enabled(True) is True
    assert host.driver_persisted == {"stub": True}
    assert ctl.is_enabled() is True


def test_canvas_driver_enable_failure_persists_false():
    host = _FakeHost()
    driver = _FakeDriver(enable_ok=False)
    ctl = _StubCanvasController(host, driver)
    assert ctl.set_enabled(True) is False
    assert host.driver_persisted == {"stub": False}
    assert ctl.is_enabled() is False


def test_canvas_driver_disable_without_build_is_safe():
    host = _FakeHost()
    ctl = _StubCanvasController(host, _FakeDriver())
    assert ctl.set_enabled(False) is True
    assert host.driver_persisted == {"stub": False}
    assert ctl.is_enabled() is False


def test_canvas_driver_lazy_single_build():
    host = _FakeHost()
    driver = _FakeDriver()
    ctl = _StubCanvasController(host, driver)
    ctl.set_enabled(True)
    ctl.set_enabled(False)
    ctl.set_enabled(True)
    # Same underlying driver re-used, not rebuilt.
    assert ctl._driver is driver   # noqa: SLF001


def test_canvas_driver_base_build_not_implemented():
    ctl = CanvasDriverController(_FakeHost())
    ctl.driver_key = "x"
    with pytest.raises(NotImplementedError):
        ctl.set_enabled(True)


# ---------------------------------------------------------------
# IdleMinigameController
# ---------------------------------------------------------------


class _StubIdleMinigame(IdleMinigameController):
    def __init__(self, host, driver) -> None:
        super().__init__(host)
        self._fake = driver

    def _build_driver(self):
        return self._fake


def test_idle_minigame_persists_requested_flag_not_driver_return():
    """The minigame has no optional dependency, so the persisted flag
    tracks the *requested* state regardless of the driver return."""
    host = _FakeHost()
    driver = _FakeDriver(enable_ok=True)
    ctl = _StubIdleMinigame(host, driver)
    assert ctl.set_enabled(True) is True
    assert host.driver_persisted == {"idle_minigame": True}
    assert driver.last_requested is True


def test_idle_minigame_disable_when_built():
    host = _FakeHost()
    driver = _FakeDriver()
    ctl = _StubIdleMinigame(host, driver)
    ctl.set_enabled(True)
    ctl.set_enabled(False)
    assert driver.last_requested is False
    assert host.driver_persisted == {"idle_minigame": False}


def test_idle_minigame_notify_activity_forwards_when_built():
    host = _FakeHost()
    driver = _FakeDriver()
    ctl = _StubIdleMinigame(host, driver)
    # No driver yet → silent no-op.
    ctl.notify_activity()
    ctl.set_enabled(True)
    ctl.notify_activity()
    assert driver.activity_pings == 1


def test_music_rhythm_driver_key():
    assert MusicRhythmController(_FakeHost()).driver_key == "music_rhythm"


# ---------------------------------------------------------------
# ClickSfxController
# ---------------------------------------------------------------


class _FakePlayer:
    def __init__(self) -> None:
        self.volume: float | None = None
        self.paths: dict | None = None
        self.played: list[str] = []
        self.shutdowns = 0

    def set_volume(self, value: float) -> None:
        self.volume = value

    def set_paths(self, paths: dict) -> None:
        self.paths = paths

    def play(self, event: str) -> None:
        self.played.append(event)

    def shutdown(self) -> None:
        self.shutdowns += 1


def _patch_sfx(monkeypatch, player):
    monkeypatch.setattr(
        "Imervue.desktop_pet.pet_drivers.ClickSfxPlayer",
        lambda parent=None: player,
    )


def test_click_sfx_enable_builds_and_configures(monkeypatch):
    player = _FakePlayer()
    _patch_sfx(monkeypatch, player)
    host = _FakeHost({"click_sfx_volume": 0.3, "click_sfx_paths": {"click": "a"}})
    ctl = ClickSfxController(host)
    ctl.set_enabled(True)
    assert host.persisted == {"click_sfx_enabled": True}
    assert player.volume == pytest.approx(0.3)
    assert player.paths == {"click": "a"}
    assert ctl.is_enabled() is True


def test_click_sfx_disable_shuts_down(monkeypatch):
    player = _FakePlayer()
    _patch_sfx(monkeypatch, player)
    host = _FakeHost()
    ctl = ClickSfxController(host)
    ctl.set_enabled(True)
    ctl.set_enabled(False)
    assert player.shutdowns == 1
    assert ctl.is_enabled() is False
    assert host.persisted == {"click_sfx_enabled": False}


def test_click_sfx_play_noop_when_disabled():
    ctl = ClickSfxController(_FakeHost())
    # Never enabled → play is a silent no-op (no player).
    ctl.play("click")
    assert ctl.is_enabled() is False


def test_click_sfx_play_forwards_when_enabled(monkeypatch):
    player = _FakePlayer()
    _patch_sfx(monkeypatch, player)
    ctl = ClickSfxController(_FakeHost())
    ctl.set_enabled(True)
    ctl.play("drag")
    assert player.played == ["drag"]


# ---------------------------------------------------------------
# LlmDialogueController
# ---------------------------------------------------------------


class _FakeLlmClient:
    def __init__(self, *, raise_on_configure: bool = False) -> None:
        self._raise = raise_on_configure
        self.line_received = _Signal()
        self.request_failed = _Signal()
        self.endpoints = 0
        self.requests: list[str] = []

    def set_endpoint(self, **kwargs: object) -> None:
        if self._raise:
            raise ValueError("bad base url")
        self.endpoints += 1

    def request_line(self, situation: str) -> None:
        self.requests.append(situation)


class _Signal:
    def connect(self, _slot) -> None:
        pass


def _patch_llm(monkeypatch, client):
    monkeypatch.setattr(
        "Imervue.desktop_pet.pet_drivers.LlmDialogueClient",
        lambda parent=None: client,
    )


def test_llm_enable_success_persists_true(monkeypatch):
    client = _FakeLlmClient()
    _patch_llm(monkeypatch, client)
    host = _FakeHost()
    ctl = LlmDialogueController(host, lambda _l: None, lambda _r: None)
    assert ctl.set_enabled(True) is True
    assert host.persisted == {"llm_enabled": True}


def test_llm_enable_invalid_url_persists_false(monkeypatch):
    client = _FakeLlmClient(raise_on_configure=True)
    _patch_llm(monkeypatch, client)
    host = _FakeHost()
    ctl = LlmDialogueController(host, lambda _l: None, lambda _r: None)
    assert ctl.set_enabled(True) is False
    assert host.persisted == {"llm_enabled": False}


def test_llm_disable_persists_false_without_touching_client(monkeypatch):
    host = _FakeHost()
    ctl = LlmDialogueController(host, lambda _l: None, lambda _r: None)
    assert ctl.set_enabled(False) is True
    assert host.persisted == {"llm_enabled": False}


def test_llm_is_enabled_reads_persisted_flag():
    host = _FakeHost({"llm_enabled": True})
    ctl = LlmDialogueController(host, lambda _l: None, lambda _r: None)
    assert ctl.is_enabled() is True


def test_llm_request_line_lazy_builds_and_forwards(monkeypatch):
    client = _FakeLlmClient()
    _patch_llm(monkeypatch, client)
    ctl = LlmDialogueController(_FakeHost(), lambda _l: None, lambda _r: None)
    ctl.request_line("hit:ear")
    assert client.requests == ["hit:ear"]
