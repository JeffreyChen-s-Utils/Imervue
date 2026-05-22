"""Tests for the global-hotkey manager.

Split into two layers:

* **Pure helpers** (parser, validator, coercer) run without any
  pynput import — they're cheap, deterministic, and cover the
  cases where a user's typo'd hotkey spec sneaks into the
  settings file.

* **Manager lifecycle** uses a monkey-patched ``pynput.keyboard``
  stub so the real OS-level keyboard hook never actually starts
  (it would race with the developer's own keystrokes on local
  runs and demand permissions on macOS / Linux). The stub still
  validates the wiring: bindings translate to the right pynput
  map, signals fire on the right action, ``stop()`` cleans up.
"""
from __future__ import annotations

import sys
import types

import pytest

from Imervue.desktop_pet.hotkey_manager import (
    ACTION_SPEAK_NOW,
    ACTION_TOGGLE_CLICK_THROUGH,
    ACTION_TOGGLE_LOCK,
    ACTION_TOGGLE_VISIBLE,
    DEFAULT_HOTKEY_BINDINGS,
    HOTKEY_ACTIONS,
    GlobalHotkeyManager,
    coerce_bindings,
    is_valid_spec,
    to_pynput_spec,
)


# ---------------------------------------------------------------
# Pure helpers — parser
# ---------------------------------------------------------------


def test_to_pynput_spec_translates_basic_combo():
    """Canonical case — Qt-style → pynput-style."""
    assert to_pynput_spec("ctrl+shift+p") == "<ctrl>+<shift>+p"


def test_to_pynput_spec_lowercases_and_trims():
    """Users paste shortcuts from random places — uppercase /
    extra whitespace shouldn't cause a silent re-bind failure."""
    assert to_pynput_spec("CTRL + Shift + P") == "<ctrl>+<shift>+p"


def test_to_pynput_spec_collapses_modifier_aliases():
    """``Control`` / ``Win`` / ``Super`` are alternate spellings for
    the same modifiers — collapsing them keeps the pynput map keyed
    on one canonical form so duplicate bindings don't sneak in."""
    assert to_pynput_spec("control+a") == "<ctrl>+a"
    assert to_pynput_spec("win+a") == "<cmd>+a"
    assert to_pynput_spec("super+a") == "<cmd>+a"


def test_to_pynput_spec_wraps_named_final_key():
    """A multi-char final key (``space``, ``f1``) needs angle brackets
    in pynput's syntax; a single char (``p``) does not."""
    assert to_pynput_spec("ctrl+shift+space") == "<ctrl>+<shift>+<space>"
    assert to_pynput_spec("ctrl+f1") == "<ctrl>+<f1>"
    assert to_pynput_spec("ctrl+a") == "<ctrl>+a"


def test_to_pynput_spec_rejects_empty():
    with pytest.raises(ValueError):
        to_pynput_spec("")
    with pytest.raises(ValueError):
        to_pynput_spec("   ")
    with pytest.raises(ValueError):
        to_pynput_spec("+++")


def test_to_pynput_spec_rejects_trailing_modifier():
    """``ctrl+shift`` (no key after modifiers) is invalid — pynput
    can't bind on modifier-only combos, and we'd rather catch this
    here than crash the listener at start time."""
    with pytest.raises(ValueError):
        to_pynput_spec("ctrl+shift")


def test_to_pynput_spec_rejects_non_modifier_prefix():
    """``a+b`` is meaningless as a hotkey — every token before the
    final must be a modifier. Without this check, weird specs would
    sneak through and silently never fire."""
    with pytest.raises(ValueError):
        to_pynput_spec("a+b+c")


# ---------------------------------------------------------------
# Pure helpers — validator + coercer
# ---------------------------------------------------------------


def test_is_valid_spec_round_trip():
    """The validator must agree with the parser on every input."""
    for good in (
        "ctrl+p", "ctrl+shift+space", "alt+f4", "ctrl+shift+f1",
    ):
        assert is_valid_spec(good) is True
    for bad in ("", "ctrl", "ctrl+shift", "a+b", "+"):
        assert is_valid_spec(bad) is False


def test_coerce_bindings_drops_unknown_actions():
    """A binding for an action that this runtime doesn't know about
    must be ignored so a future-schema settings file doesn't crash
    an older runtime."""
    raw = {
        ACTION_TOGGLE_VISIBLE: "ctrl+p",
        "future_action_v2": "ctrl+q",
    }
    out = coerce_bindings(raw)
    assert out == {ACTION_TOGGLE_VISIBLE: "ctrl+p"}


def test_coerce_bindings_drops_invalid_specs():
    """A typo'd spec must drop, not leak through to the listener
    where it would silently never fire."""
    raw = {
        ACTION_TOGGLE_VISIBLE: "ctrl+p",
        ACTION_TOGGLE_LOCK: "ctrl+shift",   # invalid
        ACTION_SPEAK_NOW: 42,               # not a string
    }
    assert coerce_bindings(raw) == {ACTION_TOGGLE_VISIBLE: "ctrl+p"}


def test_coerce_bindings_handles_non_dict_input():
    """Garbage at the top level (None, list) must produce an empty
    dict instead of raising — same forgiving rule the rest of the
    settings loader follows."""
    assert coerce_bindings(None) == {}
    assert coerce_bindings([]) == {}
    assert coerce_bindings("ctrl+p") == {}


def test_default_bindings_are_valid():
    """Sanity guard: every shipped default must parse, otherwise
    the first-launch UX is broken."""
    for action, spec in DEFAULT_HOTKEY_BINDINGS.items():
        assert action in HOTKEY_ACTIONS
        assert is_valid_spec(spec), f"default for {action} fails to parse: {spec}"


# ---------------------------------------------------------------
# Manager lifecycle (with a pynput stub so no real hook starts)
# ---------------------------------------------------------------


class _StubGlobalHotKeys:
    """Captures the constructor map + tracks start / stop calls so
    tests can verify the wiring without spawning a real OS hook."""

    instances: list[_StubGlobalHotKeys] = []

    def __init__(self, mapping: dict[str, object]) -> None:
        self.mapping = mapping
        self.started = False
        self.stopped = False
        _StubGlobalHotKeys.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture
def stub_pynput(monkeypatch):
    """Replace ``pynput.keyboard`` with a stub for the duration of
    one test. Cleans up the import cache afterwards so other tests
    still get the real module if they want it."""
    _StubGlobalHotKeys.instances.clear()
    fake_keyboard = types.SimpleNamespace(GlobalHotKeys=_StubGlobalHotKeys)
    fake_pynput = types.ModuleType("pynput")
    fake_pynput.keyboard = fake_keyboard   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", fake_keyboard)
    yield _StubGlobalHotKeys


def test_manager_starts_with_bindings(qapp, stub_pynput):
    mgr = GlobalHotkeyManager()
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+shift+p"})
    assert mgr.start() is True
    assert mgr.is_running() is True
    inst = stub_pynput.instances[-1]
    assert "<ctrl>+<shift>+p" in inst.mapping
    assert inst.started is True
    mgr.stop()
    assert mgr.is_running() is False
    assert inst.stopped is True


def test_manager_start_without_bindings_is_noop(qapp, stub_pynput):
    """Starting with an empty map mustn't create a listener — a
    no-op listener would still hold the OS keyboard hook for
    nothing."""
    mgr = GlobalHotkeyManager()
    assert mgr.start() is False
    assert mgr.is_running() is False
    assert stub_pynput.instances == []


def test_manager_emits_signal_for_action(qapp, stub_pynput):
    """The emitter wrapped around each pynput callback must fire
    the action's signal — that's the only wiring proof that links
    a binding to an action."""
    mgr = GlobalHotkeyManager()
    received: list[str] = []
    mgr.action_triggered.connect(received.append)
    mgr.set_bindings({ACTION_TOGGLE_LOCK: "ctrl+l"})
    mgr.start()
    inst = stub_pynput.instances[-1]
    callback = next(iter(inst.mapping.values()))
    callback()
    assert received == [ACTION_TOGGLE_LOCK]
    mgr.stop()


def test_set_bindings_while_running_rebuilds_listener(qapp, stub_pynput):
    """Calling set_bindings on a running manager must stop the old
    listener and start a fresh one with the new map — otherwise an
    edit to a binding would silently never take effect."""
    mgr = GlobalHotkeyManager()
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+p"})
    mgr.start()
    old = stub_pynput.instances[-1]
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+q"})
    new = stub_pynput.instances[-1]
    assert new is not old
    assert old.stopped is True
    assert "<ctrl>+q" in new.mapping
    mgr.stop()


def test_start_is_idempotent(qapp, stub_pynput):
    """Calling start twice without an intervening stop must not
    create a second listener — pynput's hook is exclusive on
    Windows and a duplicate would silently fail to register."""
    mgr = GlobalHotkeyManager()
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+p"})
    assert mgr.start() is True
    assert mgr.start() is True   # second call — already running
    assert len(stub_pynput.instances) == 1
    mgr.stop()


def test_stop_when_not_running_is_safe(qapp, stub_pynput):
    """``stop()`` must tolerate being called on a never-started
    manager — the UI 'Disable hotkeys' path can hit this when the
    feature was never enabled."""
    mgr = GlobalHotkeyManager()
    mgr.stop()   # must not raise
    assert mgr.is_running() is False


def test_start_returns_false_when_pynput_missing(qapp, monkeypatch):
    """Forcing the import to fail must surface as ``start() ->
    False`` rather than an exception, so the workspace can show
    the friendly "pip install pynput" message."""
    # Block the import path
    monkeypatch.setitem(sys.modules, "pynput", None)
    mgr = GlobalHotkeyManager()
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+p"})
    assert mgr.start() is False
    assert mgr.is_running() is False


def test_listener_creation_failure_returns_false(qapp, monkeypatch):
    """If pynput's listener constructor raises (e.g. macOS denies
    accessibility), ``start`` must catch it and report failure
    rather than propagating the exception into the workspace."""
    class _RaisingHotKeys:
        def __init__(self, _mapping):
            raise RuntimeError("hook denied")

    fake_keyboard = types.SimpleNamespace(GlobalHotKeys=_RaisingHotKeys)
    fake_pynput = types.ModuleType("pynput")
    fake_pynput.keyboard = fake_keyboard   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", fake_keyboard)

    mgr = GlobalHotkeyManager()
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+p"})
    assert mgr.start() is False
    assert mgr.is_running() is False


def test_shutdown_alias_calls_stop(qapp, stub_pynput):
    """``shutdown`` is the lifecycle method other drivers expose;
    aliasing it to stop keeps the pet_window's teardown loop
    uniform."""
    mgr = GlobalHotkeyManager()
    mgr.set_bindings({ACTION_TOGGLE_VISIBLE: "ctrl+p"})
    mgr.start()
    mgr.shutdown()
    assert mgr.is_running() is False
    assert stub_pynput.instances[-1].stopped is True


def test_action_constants_match_canonical_list():
    """Cross-check the four ``ACTION_*`` constants match the
    canonical tuple — drift would mean a binding for an action
    that no longer exists."""
    assert set(HOTKEY_ACTIONS) == {
        ACTION_TOGGLE_VISIBLE,
        ACTION_TOGGLE_LOCK,
        ACTION_TOGGLE_CLICK_THROUGH,
        ACTION_SPEAK_NOW,
    }
