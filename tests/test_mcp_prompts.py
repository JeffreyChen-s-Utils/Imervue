"""Tests for the MCP prompt templates and server prompt methods."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.prompts import get_prompt, list_prompts


def _save(path):
    Image.fromarray(np.full((24, 24, 3), 120, dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def test_list_prompts_has_expected():
    names = {p["name"] for p in list_prompts()}
    assert {"caption_image", "suggest_edits"} <= names
    caption = next(p for p in list_prompts() if p["name"] == "caption_image")
    assert caption["arguments"][0]["name"] == "path"


def test_caption_image_embeds_image(tmp_path):
    result = get_prompt("caption_image", {"path": _save(tmp_path / "a.png")})
    blocks = [m["content"]["type"] for m in result["messages"]]
    assert "text" in blocks and "image" in blocks
    image_msg = next(m for m in result["messages"] if m["content"]["type"] == "image")
    assert image_msg["content"]["mimeType"] == "image/png"
    assert image_msg["content"]["data"]


def test_suggest_edits_builds_text(tmp_path):
    result = get_prompt("suggest_edits", {"path": _save(tmp_path / "a.png"), "style": "portrait"})
    text = result["messages"][0]["content"]["text"]
    assert "portrait" in text and "clipping" in text.lower()


def test_unknown_prompt_raises():
    with pytest.raises(ValueError):
        get_prompt("nope", {})


def test_missing_path_raises():
    with pytest.raises(ValueError):
        get_prompt("caption_image", {})


# --- server wiring ---------------------------------------------------------

def _server():
    from Imervue.mcp_server.server import MCPServer
    from Imervue.mcp_server.tools import register_default_tools
    server = MCPServer()
    register_default_tools(server)
    return server


def test_initialize_advertises_prompts():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert "prompts" in resp["result"]["capabilities"]


def test_prompts_list_method():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 2, "method": "prompts/list"})
    names = {p["name"] for p in resp["result"]["prompts"]}
    assert {"caption_image", "suggest_edits"} <= names


def test_prompts_get_method(tmp_path):
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 3, "method": "prompts/get",
        "params": {"name": "suggest_edits", "arguments": {"path": _save(tmp_path / "a.png")}},
    })
    assert "messages" in resp["result"]


def test_prompts_get_unknown_is_error():
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "prompts/get",
        "params": {"name": "ghost", "arguments": {}},
    })
    assert resp["error"]["code"] == -32602
