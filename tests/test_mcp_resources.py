"""Tests for MCP resources (list / templates / read) and server wiring."""
from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.resources import (
    ResourceError,
    image_uri,
    list_resource_templates,
    list_resources,
    read_resource,
)


def _save(path):
    Image.fromarray(np.full((24, 24, 3), 120, dtype=np.uint8), "RGB").save(str(path))
    return str(path)


# --- pure functions --------------------------------------------------------

def test_list_resources_lists_images(tmp_path):
    _save(tmp_path / "a.png")
    _save(tmp_path / "b.jpg")
    (tmp_path / "notes.txt").write_text("x")
    result = list_resources(str(tmp_path))
    names = {r["name"] for r in result["resources"]}
    assert names == {"a.png", "b.jpg"}
    assert "nextCursor" not in result   # small folder fits one page


def test_list_resources_no_root_is_empty():
    assert list_resources(None) == {"resources": []}


def test_invalid_cursor_raises(tmp_path):
    with pytest.raises(ResourceError) as exc:
        list_resources(str(tmp_path), cursor="!!!notbase64!!!")
    assert exc.value.code == -32602


def test_templates_list():
    templates = list_resource_templates()["resourceTemplates"]
    uris = {t["uriTemplate"] for t in templates}
    assert any(u.endswith("{path}") for u in uris)
    assert any(u.endswith("{path}/metadata") for u in uris)


def test_read_thumbnail_blob(tmp_path):
    uri = image_uri(_save(tmp_path / "a.png"))
    contents = read_resource(uri)["contents"][0]
    assert contents["mimeType"] == "image/png"
    assert contents["blob"]


def test_read_metadata_json(tmp_path):
    uri = image_uri(_save(tmp_path / "a.png")) + "/metadata"
    contents = read_resource(uri)["contents"][0]
    assert contents["mimeType"] == "application/json"
    meta = json.loads(contents["text"])
    assert meta["width"] == 24 and meta["height"] == 24


def test_read_bad_scheme_raises():
    with pytest.raises(ResourceError) as exc:
        read_resource("file:///etc/passwd")
    assert exc.value.code == -32602


def test_read_missing_file_raises():
    with pytest.raises(ResourceError) as exc:
        read_resource(image_uri("/no/such/image.png"))
    assert exc.value.code == -32002


def test_read_rejects_traversal():
    from urllib.parse import quote
    from Imervue.mcp_server.resources import _SCHEME
    with pytest.raises(ResourceError) as exc:
        read_resource(_SCHEME + quote("../secret.png", safe=""))
    assert exc.value.code == -32602


# --- server wiring ---------------------------------------------------------

def _server(root=None):
    from Imervue.mcp_server.server import MCPServer
    from Imervue.mcp_server.tools import register_default_tools
    server = MCPServer(resource_root=root)
    register_default_tools(server)
    return server


def test_initialize_advertises_resources():
    resp = _server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert "resources" in resp["result"]["capabilities"]


def test_resources_list_method(tmp_path):
    _save(tmp_path / "a.png")
    resp = _server(str(tmp_path)).handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
    assert len(resp["result"]["resources"]) == 1


def test_resources_templates_method():
    resp = _server().handle_message(
        {"jsonrpc": "2.0", "id": 3, "method": "resources/templates/list"})
    assert resp["result"]["resourceTemplates"]


def test_resources_read_method(tmp_path):
    uri = image_uri(_save(tmp_path / "a.png"))
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": uri}})
    assert resp["result"]["contents"][0]["blob"]


def test_resources_read_bad_uri_is_error():
    resp = _server().handle_message({
        "jsonrpc": "2.0", "id": 5, "method": "resources/read",
        "params": {"uri": "http://x"}})
    assert resp["error"]["code"] == -32602
