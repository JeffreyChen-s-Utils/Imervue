"""Tests for the MCP prompt templates and server prompt methods."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.prompts import (
    _salient_placement,
    _third_label,
    get_prompt,
    list_prompts,
)


def _save(path):
    Image.fromarray(np.full((24, 24, 3), 120, dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def _is_region_label(text: str) -> bool:
    return text == "the centre of the frame" or (
        text.startswith("the ") and text.endswith(" region")
    )


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


def test_list_prompts_includes_new_prompts():
    names = {p["name"] for p in list_prompts()}
    assert {"analyze_composition", "flag_issues"} <= names


def test_analyze_composition_embeds_image_and_critique(tmp_path):
    result = get_prompt("analyze_composition", {"path": _save(tmp_path / "a.png")})
    blocks = [m["content"]["type"] for m in result["messages"]]
    assert "text" in blocks and "image" in blocks
    text = next(m["content"]["text"] for m in result["messages"]
                if m["content"]["type"] == "text")
    assert "rule-of-thirds" in text
    # Flat grey frame → saliency sits in the centre.
    assert "centre of the frame" in text


def test_analyze_composition_focus_appears_in_text(tmp_path):
    result = get_prompt(
        "analyze_composition",
        {"path": _save(tmp_path / "a.png"), "focus": "balance"},
    )
    text = result["messages"][0]["content"]["text"]
    assert "focusing on balance" in text


def test_flag_issues_builds_technical_text(tmp_path):
    result = get_prompt("flag_issues", {"path": _save(tmp_path / "a.png")})
    text = result["messages"][0]["content"]["text"]
    assert "Sharpness score" in text
    assert "clipping" in text.lower()
    assert "severity" in text.lower()


def test_analyze_composition_missing_path_raises():
    with pytest.raises(ValueError):
        get_prompt("analyze_composition", {})


def test_flag_issues_missing_path_raises():
    with pytest.raises(ValueError):
        get_prompt("flag_issues", {})


# --- placement helpers -----------------------------------------------------


@pytest.mark.parametrize("nx,ny,expected", [
    (0.5, 0.5, "the centre of the frame"),
    (0.1, 0.1, "the upper-left region"),
    (0.9, 0.9, "the lower-right region"),
    (0.1, 0.9, "the lower-left region"),
    (0.9, 0.1, "the upper-right region"),
    (0.5, 0.1, "the upper region"),
    (0.9, 0.5, "the right region"),
])
def test_third_label_maps_coordinates(nx, ny, expected):
    assert _third_label(nx, ny) == expected


def test_salient_placement_flat_image_is_centre():
    arr = np.full((20, 20, 4), 255, dtype=np.uint8)
    arr[..., :3] = 128
    assert _salient_placement(arr) == "the centre of the frame"


def test_salient_placement_returns_valid_label_for_content():
    arr = np.full((32, 32, 4), 255, dtype=np.uint8)
    arr[..., :3] = 40
    arr[4:14, 4:14, :3] = 230  # bright block, upper-left
    assert _is_region_label(_salient_placement(arr))


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


def test_prompts_get_analyze_composition_embeds_image(tmp_path):
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 5, "method": "prompts/get",
        "params": {"name": "analyze_composition",
                   "arguments": {"path": _save(tmp_path / "a.png")}},
    })
    types = {m["content"]["type"] for m in resp["result"]["messages"]}
    assert "image" in types
