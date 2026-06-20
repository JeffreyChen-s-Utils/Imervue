"""Tests for MCP tool output schemas, structured content and annotations.

Covers the MCP 2025-11-25 tools upgrade: every default tool advertises an
``outputSchema`` and ``annotations`` in ``tools/list``, ``tools/call``
surfaces dict results as ``structuredContent``, and that structured payload
conforms (required keys present) to the declared schema.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from Imervue.mcp_server.server import MCPServer, _tool_success
from Imervue.mcp_server.tool_schemas import TOOL_METADATA
from Imervue.mcp_server.tools import _TOOL_DEFINITIONS, register_default_tools

_WRITE_TOOLS = {
    "convert_format", "puppet_from_png", "extract_video_frame",
    "apply_watermark", "apply_frame", "build_collage", "crop_image",
}


@pytest.fixture
def server() -> MCPServer:
    s = MCPServer()
    register_default_tools(s)
    return s


@pytest.fixture
def sample_png(tmp_path):
    from PIL import Image
    path = tmp_path / "sample.png"
    arr = np.zeros((24, 32, 3), dtype=np.uint8)
    arr[..., 0] = 200
    arr[..., 1] = 120
    Image.fromarray(arr).save(path, format="PNG")
    return path


def _request(method, params=None, *, msg_id=1):
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}


def _tools_by_name(server):
    response = server.handle_message(_request("tools/list"))
    return {t["name"]: t for t in response["result"]["tools"]}


# ---------------------------------------------------------------------------
# Metadata / registration parity
# ---------------------------------------------------------------------------


def test_metadata_covers_exactly_the_registered_tools():
    """Every registered tool has schema metadata and there are no stale
    entries — adding a tool without a schema fails this gate."""
    registered = {entry["name"] for entry in _TOOL_DEFINITIONS}
    assert set(TOOL_METADATA) == registered


def test_each_metadata_entry_has_schema_and_annotations():
    for name, meta in TOOL_METADATA.items():
        assert "output_schema" in meta, name
        assert "annotations" in meta, name


# ---------------------------------------------------------------------------
# tools/list advertises outputSchema + annotations
# ---------------------------------------------------------------------------


def test_every_tool_advertises_output_schema(server):
    for name, tool in _tools_by_name(server).items():
        schema = tool.get("outputSchema")
        assert schema is not None, f"{name} has no outputSchema"
        assert schema["type"] == "object"
        assert "properties" in schema


def test_every_tool_advertises_annotations(server):
    for name, tool in _tools_by_name(server).items():
        annotations = tool.get("annotations")
        assert annotations is not None, f"{name} has no annotations"
        assert isinstance(annotations["readOnlyHint"], bool)
        assert isinstance(annotations["idempotentHint"], bool)
        assert isinstance(annotations["title"], str) and annotations["title"]


def test_open_world_hint_is_always_false(server):
    """No Imervue tool touches the network, so none claim the open world."""
    for tool in _tools_by_name(server).values():
        assert tool["annotations"]["openWorldHint"] is False


@pytest.mark.parametrize("name", [
    "read_image_metadata", "sharpness_score", "image_statistics",
    "read_histogram", "find_similar", "reverse_geocode",
])
def test_read_only_tools_are_flagged_read_only(server, name):
    annotations = _tools_by_name(server)[name]["annotations"]
    assert annotations["readOnlyHint"] is True
    assert annotations["destructiveHint"] is False


@pytest.mark.parametrize("name", sorted(_WRITE_TOOLS))
def test_write_tools_are_flagged_destructive(server, name):
    annotations = _tools_by_name(server)[name]["annotations"]
    assert annotations["readOnlyHint"] is False
    assert annotations["destructiveHint"] is True


# ---------------------------------------------------------------------------
# structuredContent on tools/call
# ---------------------------------------------------------------------------


def test_tools_call_includes_structured_content(server):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "reverse_geocode",
         "arguments": {"latitude": 48.85, "longitude": 2.35}},
    ))
    result = response["result"]
    assert "structuredContent" in result
    # The structured payload round-trips with the text serialisation.
    assert result["structuredContent"] == json.loads(result["content"][0]["text"])


def test_tool_success_helper_adds_structured_content_for_dicts():
    wrapped = _tool_success({"a": 1, "b": [2, 3]})
    assert wrapped["structuredContent"] == {"a": 1, "b": [2, 3]}


def test_tool_success_helper_omits_structured_content_for_strings():
    wrapped = _tool_success("plain text")
    assert "structuredContent" not in wrapped
    assert wrapped["content"][0]["text"] == "plain text"


def test_tool_error_path_has_no_structured_content(server):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "read_image_metadata", "arguments": {"path": "/no/such.png"}},
    ))
    result = response["result"]
    assert result["isError"] is True
    assert "structuredContent" not in result


# ---------------------------------------------------------------------------
# Structured payload conforms to the declared schema (required keys present)
# ---------------------------------------------------------------------------


def _assert_conforms(structured, schema):
    assert schema["type"] == "object"
    assert isinstance(structured, dict)
    for key in schema.get("required", []):
        assert key in structured, f"result missing required key {key!r}"


def test_reverse_geocode_conforms_to_schema(server):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "reverse_geocode",
         "arguments": {"latitude": 35.68, "longitude": 139.69}},
    ))
    _assert_conforms(
        response["result"]["structuredContent"],
        TOOL_METADATA["reverse_geocode"]["output_schema"],
    )


@pytest.mark.parametrize("name", [
    "read_image_metadata", "read_xmp_tags", "sharpness_score",
    "image_statistics", "quality_metrics", "read_histogram",
    "ocr_text", "image_thumbnail",
])
def test_image_tool_structured_content_conforms(server, sample_png, name):
    response = server.handle_message(_request(
        "tools/call", {"name": name, "arguments": {"path": str(sample_png)}},
    ))
    result = response["result"]
    assert result["isError"] is False
    _assert_conforms(
        result["structuredContent"], TOOL_METADATA[name]["output_schema"],
    )


def test_apply_watermark_structured_content_conforms(server, sample_png, tmp_path):
    dst = tmp_path / "marked.png"
    response = server.handle_message(_request(
        "tools/call",
        {"name": "apply_watermark",
         "arguments": {"source": str(sample_png),
                       "destination": str(dst), "text": "mark"}},
    ))
    result = response["result"]
    assert result["isError"] is False
    _assert_conforms(
        result["structuredContent"], TOOL_METADATA["apply_watermark"]["output_schema"],
    )
    assert dst.exists()


def test_apply_frame_structured_content_conforms(server, sample_png, tmp_path):
    dst = tmp_path / "framed.png"
    response = server.handle_message(_request(
        "tools/call",
        {"name": "apply_frame",
         "arguments": {"source": str(sample_png),
                       "destination": str(dst), "border": 8}},
    ))
    result = response["result"]
    assert result["isError"] is False
    _assert_conforms(
        result["structuredContent"], TOOL_METADATA["apply_frame"]["output_schema"],
    )
    assert dst.exists()


def test_build_collage_structured_content_conforms(server, sample_png, tmp_path):
    dst = tmp_path / "collage.png"
    response = server.handle_message(_request(
        "tools/call",
        {"name": "build_collage",
         "arguments": {"sources": [str(sample_png), str(sample_png)],
                       "destination": str(dst), "columns": 2}},
    ))
    result = response["result"]
    assert result["isError"] is False
    _assert_conforms(
        result["structuredContent"], TOOL_METADATA["build_collage"]["output_schema"],
    )
    assert dst.exists()


def test_crop_image_structured_content_conforms(server, sample_png, tmp_path):
    dst = tmp_path / "crop.png"
    response = server.handle_message(_request(
        "tools/call",
        {"name": "crop_image",
         "arguments": {"source": str(sample_png), "destination": str(dst),
                       "x": 2, "y": 2, "width": 8, "height": 8}},
    ))
    result = response["result"]
    assert result["isError"] is False
    _assert_conforms(
        result["structuredContent"], TOOL_METADATA["crop_image"]["output_schema"],
    )
    assert dst.exists()


def test_list_images_structured_content_conforms(server, sample_png):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "list_images", "arguments": {"folder": str(sample_png.parent)}},
    ))
    structured = response["result"]["structuredContent"]
    _assert_conforms(structured, TOOL_METADATA["list_images"]["output_schema"])
    assert structured["count"] >= 1
