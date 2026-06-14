"""Tests for the localhost webhook receiver.

Three layers:

* **Pure helpers** (``parse_payload``, ``bearer_token``) — easy
  to test without sockets.
* **Receiver lifecycle** (``start`` / ``stop`` / ``dispatch``) —
  no HTTP, just exercises the Qt signal pipeline + the
  thread / server lifecycle through stubs.
* **End-to-end HTTP** uses a real ``ThreadingHTTPServer`` bound
  to a free port; we make a few stdlib ``http.client`` calls
  against it to verify the full request → signal path.
"""
from __future__ import annotations

import http.client
import json
import socket
import time

import pytest

from Imervue.desktop_pet.webhook_server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    WebhookCommand,
    WebhookReceiver,
    bearer_token,
    parse_payload,
)


# ---------------------------------------------------------------
# parse_payload
# ---------------------------------------------------------------


def test_parse_payload_full():
    cmd = parse_payload({"group": "Wave", "speech": "Hi!"})
    assert cmd == WebhookCommand(group="Wave", speech="Hi!")


def test_parse_payload_group_only():
    """Common case: external tool just wants a motion."""
    cmd = parse_payload({"group": "Wave"})
    assert cmd is not None
    assert cmd.group == "Wave"
    assert cmd.speech == ""


def test_parse_payload_speech_only():
    cmd = parse_payload({"speech": "Welcome"})
    assert cmd is not None
    assert cmd.group == ""
    assert cmd.speech == "Welcome"


def test_parse_payload_both_empty_returns_none():
    """Empty / whitespace-only fields → no command — avoids the
    pet doing literally nothing on a "successful" trigger."""
    assert parse_payload({"group": "", "speech": ""}) is None
    assert parse_payload({"group": "  ", "speech": "  "}) is None
    assert parse_payload({}) is None


def test_parse_payload_non_dict_returns_none():
    assert parse_payload(None) is None
    assert parse_payload([]) is None
    assert parse_payload("hello") is None
    assert parse_payload(42) is None


def test_parse_payload_non_string_fields_treated_as_empty():
    """A malformed POST with numeric fields → drop the bad value,
    keep the good one. Defends against careless callers."""
    cmd = parse_payload({"group": 42, "speech": "Hi"})
    assert cmd is not None
    assert cmd.group == ""
    assert cmd.speech == "Hi"


def test_parse_payload_strips_whitespace():
    cmd = parse_payload({"group": "  Wave  ", "speech": "  Hi  "})
    assert cmd == WebhookCommand(group="Wave", speech="Hi")


# ---------------------------------------------------------------
# bearer_token
# ---------------------------------------------------------------


def test_bearer_token_extracts_value():
    assert bearer_token("Bearer abc123") == "abc123"


def test_bearer_token_case_insensitive_scheme():
    """RFC 6750 allows any case for the scheme name — accept it."""
    assert bearer_token("bearer abc") == "abc"
    assert bearer_token("BEARER abc") == "abc"


def test_bearer_token_missing_returns_empty():
    assert bearer_token("") == ""
    assert bearer_token(None) == ""


def test_bearer_token_malformed_returns_empty():
    """Non-Bearer schemes / missing value → empty so the equality
    check against the expected token fails."""
    assert bearer_token("Basic dXNlcjpwYXNz") == ""
    assert bearer_token("Bearer") == ""
    assert bearer_token("just-a-token") == ""


# ---------------------------------------------------------------
# WebhookReceiver — lifecycle (no socket)
# ---------------------------------------------------------------


def test_receiver_starts_not_running(qapp):
    receiver = WebhookReceiver()
    try:
        assert receiver.is_running() is False
        assert receiver.port() == DEFAULT_PORT
        assert receiver.token() == ""
    finally:
        receiver.deleteLater()


def test_set_endpoint_clamps_empty_port(qapp):
    receiver = WebhookReceiver()
    try:
        receiver.set_endpoint(port=0, token="abc")   # noqa: S106  # test fixture, not a real credential
        assert receiver.port() == DEFAULT_PORT
        assert receiver.token() == "abc"
    finally:
        receiver.deleteLater()


def test_dispatch_emits_signal(qapp):
    """``dispatch`` is the public hook the HTTP handler calls;
    tests reach it directly without binding a socket."""
    receiver = WebhookReceiver()
    captured: list[tuple[str, str]] = []
    receiver.command_received.connect(
        lambda group, speech: captured.append((group, speech)),
    )
    try:
        receiver.dispatch(WebhookCommand(group="Wave", speech="Hi"))
        assert captured == [("Wave", "Hi")]
    finally:
        receiver.deleteLater()


def test_stop_when_not_running_is_safe(qapp):
    receiver = WebhookReceiver()
    receiver.stop()
    assert receiver.is_running() is False


# ---------------------------------------------------------------
# End-to-end HTTP — real server on a free port
# ---------------------------------------------------------------


def _free_port() -> int:
    """Ask the OS for an available port — avoids hard-coded
    constants that might clash with other tests / dev servers."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _start_on_free_port(receiver, token: str, attempts: int = 5) -> int:
    """Bind *receiver* to a fresh free port, retrying to dodge the inherent
    race between probing a free port and binding it.

    ``_free_port`` closes its probe socket before returning the number, so under
    full-suite load another binder can grab that port in the gap, making
    ``start()`` fail — the source of the rare CI flakiness. Retrying with a new
    port each time makes a repeated collision astronomically unlikely.
    """
    for _ in range(attempts):
        port = _free_port()
        receiver.set_endpoint(port=port, token=token)
        if receiver.start():
            return port
    raise RuntimeError("could not bind the webhook receiver to a free port")


def _wait_for(qapp, predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return predicate()


@pytest.fixture
def running_receiver(qapp):
    receiver = WebhookReceiver()
    port = _start_on_free_port(receiver, token="")
    yield receiver, port
    receiver.stop()
    receiver.deleteLater()


def _post_json(port: int, path: str, body: dict, headers: dict | None = None):
    conn = http.client.HTTPConnection(DEFAULT_HOST, port, timeout=5.0)
    try:
        payload = json.dumps(body).encode("utf-8")
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        conn.request("POST", path, body=payload, headers=request_headers)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_e2e_trigger_emits_signal(qapp, running_receiver):
    receiver, port = running_receiver
    captured: list[tuple[str, str]] = []
    receiver.command_received.connect(
        lambda group, speech: captured.append((group, speech)),
    )
    status, _ = _post_json(port, "/trigger", {"group": "Wave"})
    assert status == 200
    assert _wait_for(qapp, lambda: bool(captured))
    assert captured == [("Wave", "")]


def test_e2e_invalid_path_returns_404(qapp, running_receiver):
    _, port = running_receiver
    status, _ = _post_json(port, "/wrong", {"group": "Wave"})
    assert status == 404


def test_e2e_empty_body_returns_400(qapp, running_receiver):
    _, port = running_receiver
    conn = http.client.HTTPConnection(DEFAULT_HOST, port, timeout=5.0)
    try:
        conn.request("POST", "/trigger", body=b"", headers={
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        assert resp.status == 400
    finally:
        conn.close()


def test_e2e_invalid_json_returns_400(qapp, running_receiver):
    _, port = running_receiver
    conn = http.client.HTTPConnection(DEFAULT_HOST, port, timeout=5.0)
    try:
        conn.request("POST", "/trigger", body=b"not json", headers={
            "Content-Type": "application/json",
            "Content-Length": "8",
        })
        resp = conn.getresponse()
        assert resp.status == 400
    finally:
        conn.close()


def test_e2e_empty_command_returns_400(qapp, running_receiver):
    _, port = running_receiver
    status, _ = _post_json(port, "/trigger", {})
    assert status == 400


def test_e2e_health_endpoint(qapp, running_receiver):
    _, port = running_receiver
    conn = http.client.HTTPConnection(DEFAULT_HOST, port, timeout=5.0)
    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read().decode("utf-8"))
        assert body == {"ok": True}
    finally:
        conn.close()


def test_e2e_auth_required_when_token_set(qapp):
    receiver = WebhookReceiver()
    port = _start_on_free_port(receiver, token="s3cret")   # noqa: S106  # test fixture, not a real credential
    try:
        # No header → 401.
        status, _ = _post_json(port, "/trigger", {"group": "Wave"})
        assert status == 401
        # Wrong token → 401.
        status, _ = _post_json(
            port, "/trigger", {"group": "Wave"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert status == 401
        # Right token → 200.
        status, _ = _post_json(
            port, "/trigger", {"group": "Wave"},
            headers={"Authorization": "Bearer s3cret"},
        )
        assert status == 200
    finally:
        receiver.stop()
        receiver.deleteLater()


def test_e2e_start_handles_invalid_port(qapp):
    """An out-of-range port (>65535) must surface as a False
    start, not a crash. Catches the OSError path."""
    receiver = WebhookReceiver()
    try:
        receiver.set_endpoint(port=99999)
        assert receiver.start() is False
        assert receiver.is_running() is False
    finally:
        receiver.deleteLater()
