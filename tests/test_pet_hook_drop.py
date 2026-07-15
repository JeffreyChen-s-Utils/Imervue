"""Tests for OBS / Twitch hooks reflecting a dropped connection.

OBS is_running only checked "a client object exists", so it read connected
forever after OBS closed. Twitch's read loop broke on a drop without closing the
socket or signalling the state change. Both are driven unbound on fakes.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

from Imervue.desktop_pet.obs_event_hook import ObsEventClient
from Imervue.desktop_pet.twitch_chat_hook import TwitchChatClient


def test_obs_is_running_false_without_a_client():
    assert ObsEventClient.is_running(SimpleNamespace(_client=None)) is False


def test_obs_is_running_reflects_the_websocket_connected_flag():
    dropped = SimpleNamespace(_client=SimpleNamespace(ws=SimpleNamespace(connected=False)))
    live = SimpleNamespace(_client=SimpleNamespace(ws=SimpleNamespace(connected=True)))
    assert ObsEventClient.is_running(dropped) is False
    assert ObsEventClient.is_running(live) is True


def test_obs_is_running_falls_back_when_ws_not_introspectable():
    assert ObsEventClient.is_running(SimpleNamespace(_client=SimpleNamespace())) is True


def test_twitch_run_closes_socket_and_signals_drop():
    closed: list = []
    signalled: list = []
    fake = SimpleNamespace(
        _sock=SimpleNamespace(recv=lambda _n: b"", close=lambda: closed.append(True)),
        _stop_flag=threading.Event(),          # not set → a genuine drop
        connection_state_changed=SimpleNamespace(emit=signalled.append),
    )
    TwitchChatClient._run(fake)
    assert closed == [True]
    assert signalled == [False]                # UI learns of the drop


def test_twitch_run_does_not_signal_when_explicitly_stopped():
    stop = threading.Event()
    stop.set()
    signalled: list = []
    fake = SimpleNamespace(
        _sock=SimpleNamespace(recv=lambda _n: b"", close=lambda: None),
        _stop_flag=stop,
        connection_state_changed=SimpleNamespace(emit=signalled.append),
    )
    TwitchChatClient._run(fake)
    assert signalled == []                      # stop() owns that signal
