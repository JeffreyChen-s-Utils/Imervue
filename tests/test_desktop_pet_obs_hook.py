"""Tests for the OBS event hook.

Two layers, mirroring the hotkey-manager test split:

* **Pure helper** :func:`obs_event_to_group` is a stateless string-
  to-string mapping; trivial to test without any network or library
  import.
* **Client lifecycle** uses a monkey-patched ``obswebsocket.obsws``
  stub so no real WebSocket is opened — that would need a running
  OBS instance. The stub still verifies the wiring: connect /
  disconnect calls, event-callback registration, signal marshalling
  to the Qt thread.
"""
from __future__ import annotations

import sys
import types

import pytest

from Imervue.desktop_pet.obs_event_hook import (
    DEFAULT_OBS_HOST,
    DEFAULT_OBS_PORT,
    OBS_EVENT_GROUPS,
    OBS_GROUP_RECORD,
    OBS_GROUP_SCENE,
    OBS_GROUP_STREAM,
    ObsEventClient,
    obs_event_to_group,
)


# ---------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------


def test_obs_event_to_group_handles_v4_names():
    """OBS v4 used verbose event names like ``RecordingStarted`` —
    the substring matcher must still resolve them."""
    assert obs_event_to_group("RecordingStarted") == OBS_GROUP_RECORD
    assert obs_event_to_group("RecordingStopped") == OBS_GROUP_RECORD
    assert obs_event_to_group("StreamingStarted") == OBS_GROUP_STREAM
    assert obs_event_to_group("SwitchScenes") == OBS_GROUP_SCENE


def test_obs_event_to_group_handles_v5_names():
    """OBS v5 collapsed start / stop into state-changed events."""
    assert obs_event_to_group("RecordStateChanged") == OBS_GROUP_RECORD
    assert obs_event_to_group("StreamStateChanged") == OBS_GROUP_STREAM
    assert obs_event_to_group("CurrentProgramSceneChanged") == OBS_GROUP_SCENE


def test_obs_event_to_group_filters_transition_events():
    """SceneTransitionStarted / SceneTransitionEnded fire alongside
    the actual scene-switch event. Without this filter the pet would
    play the Scene motion twice on every cut."""
    assert obs_event_to_group("SceneTransitionStarted") is None
    assert obs_event_to_group("SceneTransitionEnded") is None
    assert obs_event_to_group("CurrentSceneTransitionChanged") is None


def test_obs_event_to_group_returns_none_for_unknowns():
    """Anything not stream / record / scene → no reaction. Keeps the
    pet quiet during the (many) unrelated events OBS fires."""
    assert obs_event_to_group("Heartbeat") is None
    assert obs_event_to_group("InputVolumeChanged") is None
    assert obs_event_to_group("") is None


def test_obs_event_to_group_is_case_insensitive():
    """Defensive — caller might pass a lower / mixed-case form."""
    assert obs_event_to_group("recording_started") == OBS_GROUP_RECORD
    assert obs_event_to_group("STREAMSTATECHANGED") == OBS_GROUP_STREAM


def test_obs_event_groups_constant_lists_three():
    """If a future change adds a fourth group the workspace UI
    needs an update too; cross-check the canonical tuple here."""
    assert OBS_EVENT_GROUPS == (OBS_GROUP_STREAM, OBS_GROUP_RECORD, OBS_GROUP_SCENE)


# ---------------------------------------------------------------
# Client lifecycle
# ---------------------------------------------------------------


class _StubObsClient:
    """Records every interaction so tests can verify the wiring
    without opening a real WebSocket."""

    instances: list[_StubObsClient] = []

    def __init__(self, host: str, port: int, password: str) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.connected = False
        self.disconnected = False
        self.event_callback = None
        _StubObsClient.instances.append(self)

    def register(self, func, event=None) -> None:
        self.event_callback = func

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True


@pytest.fixture
def stub_obs(monkeypatch):
    """Replace ``obswebsocket.obsws`` with a stub for the test."""
    _StubObsClient.instances.clear()
    fake_module = types.ModuleType("obswebsocket")
    fake_module.obsws = _StubObsClient   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "obswebsocket", fake_module)
    yield _StubObsClient


def test_client_starts_with_endpoint(qapp, stub_obs):
    client = ObsEventClient()
    client.set_endpoint("example.local", 4455, "secret")   # noqa: S106  # test fixture, not a real credential
    assert client.start() is True
    assert client.is_running() is True
    inst = stub_obs.instances[-1]
    assert inst.host == "example.local"
    assert inst.port == 4455
    assert inst.password == "secret"   # noqa: S105  # test fixture, not a real credential
    assert inst.connected is True
    assert inst.event_callback is not None
    client.stop()
    assert client.is_running() is False
    assert inst.disconnected is True


def test_client_defaults_endpoint(qapp, stub_obs):
    """Without an explicit set_endpoint call, the client uses the
    documented defaults — saves a round-trip for users who run OBS
    on localhost with the default port."""
    client = ObsEventClient()
    client.start()
    inst = stub_obs.instances[-1]
    assert inst.host == DEFAULT_OBS_HOST
    assert inst.port == DEFAULT_OBS_PORT
    assert inst.password == ""
    client.stop()


def test_client_set_endpoint_clamps_blanks(qapp, stub_obs):
    """Blank host / zero port → use defaults instead. The workspace
    might pass empty values when the user clears the inputs."""
    client = ObsEventClient()
    client.set_endpoint("", 0, "")
    client.start()
    inst = stub_obs.instances[-1]
    assert inst.host == DEFAULT_OBS_HOST
    assert inst.port == DEFAULT_OBS_PORT
    client.stop()


def test_event_callback_emits_signal(qapp, stub_obs):
    """The catch-all callback must translate the event type and
    re-emit on :attr:`group_triggered`."""
    client = ObsEventClient()
    received: list[str] = []
    client.group_triggered.connect(received.append)
    client.start()
    inst = stub_obs.instances[-1]

    class _Event:
        def getType(self):
            return "RecordingStarted"
    inst.event_callback(_Event())
    assert received == [OBS_GROUP_RECORD]
    client.stop()


def test_event_callback_ignores_unmatched(qapp, stub_obs):
    """Events we don't react to → no signal at all. Otherwise
    every OBS heartbeat would chain into a motion lookup."""
    client = ObsEventClient()
    received: list[str] = []
    client.group_triggered.connect(received.append)
    client.start()
    inst = stub_obs.instances[-1]

    class _Event:
        def getType(self):
            return "Heartbeat"
    inst.event_callback(_Event())
    assert received == []
    client.stop()


def test_event_callback_falls_back_to_input_dict(qapp, stub_obs):
    """v5 events without ``getType()`` carry the type in
    ``input["eventType"]``. The dispatcher must handle both shapes
    so we don't break when obs-websocket-py rolls forward."""
    client = ObsEventClient()
    received: list[str] = []
    client.group_triggered.connect(received.append)
    client.start()
    inst = stub_obs.instances[-1]

    class _V5Event:
        input = {"eventType": "StreamStateChanged"}
    inst.event_callback(_V5Event())
    assert received == [OBS_GROUP_STREAM]
    client.stop()


def test_start_idempotent(qapp, stub_obs):
    """Calling start twice without an intervening stop is a no-op."""
    client = ObsEventClient()
    assert client.start() is True
    assert client.start() is True
    assert len(stub_obs.instances) == 1
    client.stop()


def test_stop_when_not_running_is_safe(qapp, stub_obs):
    """``stop()`` must tolerate being called on a never-started
    client — the workspace's disable path can hit this when the
    feature was never enabled."""
    client = ObsEventClient()
    client.stop()
    assert client.is_running() is False


def test_start_returns_false_when_library_missing(qapp, monkeypatch):
    """Block the import; surface as ``False`` so the workspace can
    show the friendly 'pip install obs-websocket-py' message."""
    monkeypatch.setitem(sys.modules, "obswebsocket", None)
    client = ObsEventClient()
    assert client.start() is False


def test_start_returns_false_when_connect_raises(qapp, monkeypatch):
    """Connection refused / wrong port / wrong password — all surface
    as exceptions out of ``connect()``. The client must catch and
    report failure."""
    class _RaisingClient:
        def __init__(self, *_, **__):
            pass

        def register(self, *_, **__):
            pass

        def connect(self):
            raise ConnectionRefusedError("OBS not running")

    fake_module = types.ModuleType("obswebsocket")
    fake_module.obsws = _RaisingClient   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "obswebsocket", fake_module)

    client = ObsEventClient()
    assert client.start() is False
    assert client.is_running() is False


def test_connection_state_signal_fires(qapp, stub_obs):
    """The UI mirrors the live state from this signal; both
    transitions (False → True on connect, True → False on stop)
    must emit."""
    client = ObsEventClient()
    states: list[bool] = []
    client.connection_state_changed.connect(states.append)
    client.start()
    client.stop()
    assert states == [True, False]


def test_shutdown_alias_calls_stop(qapp, stub_obs):
    client = ObsEventClient()
    client.start()
    client.shutdown()
    assert client.is_running() is False
    assert stub_obs.instances[-1].disconnected is True
