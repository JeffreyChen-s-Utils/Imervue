"""Tests for the MCP logging utility (level filtering + setLevel + emit)."""
from __future__ import annotations

import io
import json

from Imervue.mcp_server.logging import (
    DEFAULT_LEVEL,
    build_message,
    is_valid_level,
    should_emit,
)


# --- pure helpers ----------------------------------------------------------

def test_is_valid_level():
    assert is_valid_level("debug") and is_valid_level("emergency")
    assert not is_valid_level("verbose")
    assert not is_valid_level(None)


def test_should_emit_respects_floor():
    assert should_emit("error", "info")        # error >= info
    assert should_emit("info", "info")          # equal emits
    assert not should_emit("debug", "info")     # below floor
    assert not should_emit("info", "error")


def test_build_message_optional_logger():
    assert build_message("info", "hi") == {"level": "info", "data": "hi"}
    assert build_message("warning", {"k": 1}, "db") == {
        "level": "warning", "data": {"k": 1}, "logger": "db"}


def test_default_level_is_info():
    assert DEFAULT_LEVEL == "info"


# --- server wiring ---------------------------------------------------------

def _server():
    from Imervue.mcp_server.server import MCPServer
    from Imervue.mcp_server.tools import register_default_tools
    server = MCPServer()
    register_default_tools(server)
    return server


def test_initialize_advertises_logging():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert "logging" in resp["result"]["capabilities"]


def test_set_level_changes_floor():
    server = _server()
    resp = server.handle_message({
        "jsonrpc": "2.0", "id": 2, "method": "logging/setLevel",
        "params": {"level": "error"}})
    assert resp["result"] == {}
    assert server.log_level == "error"


def test_set_level_invalid_is_error():
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 3, "method": "logging/setLevel",
        "params": {"level": "loud"}})
    assert resp["error"]["code"] == -32602


def test_emit_log_respects_level():
    from Imervue.mcp_server.notifications import Notifier
    server = _server()
    stream = io.StringIO()
    server.notifier = Notifier(stream)
    server.log_level = "warning"

    server.emit_log("info", "quiet")        # below floor → nothing
    assert stream.getvalue() == ""

    server.emit_log("error", "boom", "db")
    msg = json.loads(stream.getvalue())
    assert msg["method"] == "notifications/message"
    assert msg["params"]["level"] == "error"
    assert msg["params"]["logger"] == "db"


def test_emit_log_without_notifier_is_silent():
    _server().emit_log("error", "x")   # no notifier → must not raise
