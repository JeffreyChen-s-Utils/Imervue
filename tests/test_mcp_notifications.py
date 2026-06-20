"""Tests for MCP push notifications: subscriptions + server-pushed messages."""
from __future__ import annotations

import io
import json

from Imervue.mcp_server.notifications import Notifier, SubscriptionRegistry


# --- pure building blocks --------------------------------------------------

def test_notifier_writes_notification_without_id():
    stream = io.StringIO()
    Notifier(stream).notify("notifications/resources/list_changed")
    message = json.loads(stream.getvalue())
    assert message["method"] == "notifications/resources/list_changed"
    assert "id" not in message
    assert message["jsonrpc"] == "2.0"


def test_notifier_notify_with_params():
    stream = io.StringIO()
    Notifier(stream).notify("notifications/resources/updated", {"uri": "imervue://image/x"})
    message = json.loads(stream.getvalue())
    assert message["params"]["uri"] == "imervue://image/x"


def test_notifier_send_passes_response_through():
    stream = io.StringIO()
    Notifier(stream).send({"jsonrpc": "2.0", "id": 7, "result": {}})
    assert json.loads(stream.getvalue())["id"] == 7


def test_subscription_registry():
    reg = SubscriptionRegistry()
    assert not reg.is_subscribed("a")
    reg.subscribe("a")
    reg.subscribe("b")
    assert reg.is_subscribed("a")
    assert reg.snapshot() == {"a", "b"}
    reg.unsubscribe("a")
    assert not reg.is_subscribed("a")
    reg.unsubscribe("missing")  # idempotent


# --- server wiring ---------------------------------------------------------

def _server():
    from Imervue.mcp_server.server import MCPServer
    from Imervue.mcp_server.tools import register_default_tools
    server = MCPServer()
    register_default_tools(server)
    return server


def test_initialize_advertises_subscribe():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    res = resp["result"]["capabilities"]["resources"]
    assert res["subscribe"] is True and res["listChanged"] is True


def test_subscribe_unsubscribe_methods():
    server = _server()
    uri = "imervue://image/x"
    resp = server.handle_message({
        "jsonrpc": "2.0", "id": 2, "method": "resources/subscribe",
        "params": {"uri": uri}})
    assert resp["result"] == {}
    assert server.subscriptions.is_subscribed(uri)
    server.handle_message({
        "jsonrpc": "2.0", "id": 3, "method": "resources/unsubscribe",
        "params": {"uri": uri}})
    assert not server.subscriptions.is_subscribed(uri)


def test_subscribe_missing_uri_is_error():
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "resources/subscribe", "params": {}})
    assert resp["error"]["code"] == -32602


def test_notify_resource_updated_only_when_subscribed():
    server = _server()
    stream = io.StringIO()
    server.notifier = Notifier(stream)
    uri = "imervue://image/x"

    server.notify_resource_updated(uri)        # not subscribed → nothing
    assert stream.getvalue() == ""

    server.subscriptions.subscribe(uri)
    server.notify_resource_updated(uri)
    message = json.loads(stream.getvalue())
    assert message["method"] == "notifications/resources/updated"
    assert message["params"]["uri"] == uri


def test_notify_list_changed():
    server = _server()
    stream = io.StringIO()
    server.notifier = Notifier(stream)
    server.notify_list_changed()
    assert json.loads(stream.getvalue())["method"] == "notifications/resources/list_changed"


def test_notify_without_notifier_is_silent():
    server = _server()   # no notifier set
    server.notify_list_changed()
    server.notify_resource_updated("imervue://image/x")  # must not raise


def test_resource_watcher_none_without_root():
    from Imervue.mcp_server.server import _start_resource_watcher
    assert _start_resource_watcher(_server()) is None  # no resource_root set
