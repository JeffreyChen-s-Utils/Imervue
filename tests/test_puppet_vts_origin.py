"""The VTS API server refuses web pages and caps message size.

Binding to 127.0.0.1 keeps the LAN out but not the browser: any site the user
visits may open a WebSocket to localhost. Browsers always send ``Origin``;
native trackers do not. ``_on_new_connection`` is driven unbound with fake
sockets, so no network or GL widget is needed and the file runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.puppet.vts_api import MAX_MESSAGE_BYTES, VTubeStudioServer


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)


class _Socket:
    def __init__(self, origin):
        self._origin = origin
        self.calls: list = []
        self.textMessageReceived = _Signal()
        self.disconnected = _Signal()

    def origin(self):
        return self._origin

    def close(self):
        self.calls.append("close")

    def deleteLater(self):  # noqa: N802 - mirrors Qt's camelCase API
        self.calls.append("deleteLater")

    def setMaxAllowedIncomingMessageSize(self, size):  # noqa: N802 - Qt API
        self.calls.append(("message", size))

    def setMaxAllowedIncomingFrameSize(self, size):  # noqa: N802 - Qt API
        self.calls.append(("frame", size))


def _accept(*sockets):
    pending = list(sockets)
    server = SimpleNamespace(hasPendingConnections=lambda: bool(pending),
                             nextPendingConnection=lambda: pending.pop(0))
    host = SimpleNamespace(_server=server, _sessions={}, _canvas=None,
                           _on_text=lambda *_a: None, _on_disconnect=lambda *_a: None)
    VTubeStudioServer._on_new_connection(host)
    return host._sessions


def test_native_tracker_gets_a_session_with_capped_messages():
    tracker = _Socket("")
    sessions = _accept(tracker)
    assert tracker in sessions
    assert tracker.calls == [("message", MAX_MESSAGE_BYTES), ("frame", MAX_MESSAGE_BYTES)]
    assert tracker.textMessageReceived.slots and tracker.disconnected.slots


def test_web_page_is_closed_without_a_session(caplog):
    page = _Socket("https://evil.example")
    tracker = _Socket("http://localhost:3000")
    with caplog.at_level("DEBUG", logger="Imervue"):
        sessions = _accept(page, tracker)
    assert page not in sessions
    assert page.calls == ["close", "deleteLater"]
    assert tracker in sessions
    assert any("evil.example" in r.getMessage() for r in caplog.records)
