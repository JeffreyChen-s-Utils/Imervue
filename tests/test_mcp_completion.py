"""Tests for MCP ping and completion/complete."""
from __future__ import annotations

from Imervue.mcp_server.completion import complete


def _server():
    from Imervue.mcp_server.server import MCPServer
    from Imervue.mcp_server.tools import register_default_tools
    server = MCPServer()
    register_default_tools(server)
    return server


# --- pure completion -------------------------------------------------------

def test_complete_style_argument():
    result = complete(
        {"type": "ref/prompt", "name": "suggest_edits"},
        {"name": "style", "value": "p"})
    values = result["completion"]["values"]
    assert "portrait" in values and "product" in values
    assert all(v.startswith("p") for v in values)
    assert result["completion"]["hasMore"] is False


def test_complete_unknown_argument_is_empty():
    result = complete(
        {"type": "ref/prompt", "name": "caption_image"},
        {"name": "path", "value": "x"})
    assert result["completion"]["values"] == []


def test_complete_non_prompt_ref_is_empty():
    result = complete({"type": "ref/resource", "uri": "x"}, {"name": "style", "value": ""})
    assert result["completion"]["values"] == []


# --- server wiring ---------------------------------------------------------

def test_ping_method():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp["result"] == {}


def test_initialize_advertises_completions():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    assert "completions" in resp["result"]["capabilities"]


def test_completion_complete_method():
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 3, "method": "completion/complete",
        "params": {
            "ref": {"type": "ref/prompt", "name": "suggest_edits"},
            "argument": {"name": "style", "value": "la"},
        },
    })
    assert "landscape" in resp["result"]["completion"]["values"]
