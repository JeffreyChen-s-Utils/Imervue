"""Tests for the Imervue MCP server.

Three layers of coverage:

1. **Protocol** — ``MCPServer.handle_message`` accepts well-formed
   JSON-RPC requests and returns the right shape. Notifications
   produce ``None``. Errors come back in JSON-RPC envelopes.
2. **stdio loop** — ``run()`` reads newline-delimited JSON from a
   StringIO and writes responses to another StringIO so we can
   exercise the transport without a subprocess.
3. **Tools** — each handler function in ``tools.py`` is called on
   synthetic inputs (tmp_path PNG, fake folder, etc.) and asserted
   on directly.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest

from Imervue.mcp_server.server import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    MCPServer,
    run,
)
from Imervue.mcp_server.tools import (
    convert_format,
    list_images,
    puppet_from_png,
    puppet_inspect,
    read_image_metadata,
    read_xmp_tags,
    register_default_tools,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server() -> MCPServer:
    s = MCPServer()
    register_default_tools(s)
    return s


@pytest.fixture
def sample_image(tmp_path):
    """Tiny PNG with known dimensions so metadata tests are
    deterministic without bundling a binary fixture."""
    from PIL import Image
    path = tmp_path / "sample.png"
    arr = np.zeros((32, 48, 3), dtype=np.uint8)
    arr[..., 0] = 200
    Image.fromarray(arr).save(path, format="PNG")
    return path


@pytest.fixture
def sample_rgba_image(tmp_path):
    from PIL import Image
    path = tmp_path / "sample.png"
    arr = np.zeros((20, 20, 4), dtype=np.uint8)
    arr[..., :3] = 180
    arr[..., 3] = 255
    Image.fromarray(arr, mode="RGBA").save(path, format="PNG")
    return path


# ---------------------------------------------------------------------------
# Protocol — handshake + tool list
# ---------------------------------------------------------------------------


def _request(method: str, params: dict | None = None, *, msg_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}


def test_initialize_returns_protocol_version_and_server_info(server):
    response = server.handle_message(_request("initialize"))
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert response["result"]["serverInfo"]["name"] == SERVER_NAME
    assert "tools" in response["result"]["capabilities"]


def test_tools_list_includes_every_default_tool(server):
    response = server.handle_message(_request("tools/list"))
    names = {t["name"] for t in response["result"]["tools"]}
    assert {
        "list_images", "read_image_metadata", "read_xmp_tags",
        "convert_format", "puppet_from_png", "puppet_inspect",
    } <= names


def test_each_tool_has_input_schema(server):
    response = server.handle_message(_request("tools/list"))
    for tool in response["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]


def test_notification_returns_none(server):
    """Notifications must not produce a response — clients hang
    waiting for one otherwise."""
    assert server.handle_message(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ) is None


def test_unknown_method_returns_jsonrpc_error(server):
    response = server.handle_message(_request("does/not/exist"))
    assert response["error"]["code"] == -32601


def test_non_object_message_returns_invalid_request_error(server):
    response = server.handle_message("oops")
    assert response["error"]["code"] == -32600


def test_message_missing_method_returns_invalid_request_error(server):
    response = server.handle_message({"jsonrpc": "2.0", "id": 1})
    assert response["error"]["code"] == -32600


# ---------------------------------------------------------------------------
# Protocol — tool call envelope
# ---------------------------------------------------------------------------


def test_tools_call_unknown_tool_returns_jsonrpc_error(server):
    response = server.handle_message(_request(
        "tools/call", {"name": "no_such_tool", "arguments": {}},
    ))
    assert response["error"]["code"] == -32602


def test_tools_call_returns_text_content(server, sample_image):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "read_image_metadata", "arguments": {"path": str(sample_image)}},
    ))
    content = response["result"]["content"]
    assert content[0]["type"] == "text"
    assert response["result"]["isError"] is False
    payload = json.loads(content[0]["text"])
    assert payload["width"] == 48
    assert payload["height"] == 32


def test_tools_call_wraps_handler_exception_as_tool_error(server):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "read_image_metadata", "arguments": {"path": "no/such/file.png"}},
    ))
    assert response["result"]["isError"] is True
    assert "does not exist" in response["result"]["content"][0]["text"]


def test_tools_call_bad_argument_shape_yields_tool_error(server):
    response = server.handle_message(_request(
        "tools/call",
        {"name": "read_image_metadata", "arguments": {"unexpected_field": "x"}},
    ))
    assert response["result"]["isError"] is True


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------


def test_run_loops_over_newline_delimited_messages():
    request_line = json.dumps(_request("initialize")) + "\n"
    stdin = io.StringIO(request_line)
    stdout = io.StringIO()
    run(stdin=stdin, stdout=stdout)
    out = stdout.getvalue().strip()
    response = json.loads(out)
    assert response["result"]["serverInfo"]["name"] == SERVER_NAME


def test_run_emits_parse_error_for_invalid_json():
    stdin = io.StringIO("{ not json\n")
    stdout = io.StringIO()
    run(stdin=stdin, stdout=stdout)
    response = json.loads(stdout.getvalue().strip())
    assert response["error"]["code"] == -32700


def test_run_skips_blank_lines():
    stdin = io.StringIO("\n\n" + json.dumps(_request("tools/list")) + "\n")
    stdout = io.StringIO()
    run(stdin=stdin, stdout=stdout)
    # Exactly one response, not three
    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1


def test_run_does_not_emit_for_notifications():
    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    stdin = io.StringIO(json.dumps(notification) + "\n")
    stdout = io.StringIO()
    run(stdin=stdin, stdout=stdout)
    assert stdout.getvalue() == ""


# ---------------------------------------------------------------------------
# Tool — list_images
# ---------------------------------------------------------------------------


def test_list_images_returns_images_in_folder(image_folder):
    result = list_images(image_folder)
    assert result["count"] >= 4
    names = {Path(e["path"]).name for e in result["images"]}
    assert {"alpha.png", "beta.jpg", "gamma.png", "delta.bmp"} <= names


def test_list_images_skips_non_image_files(tmp_path):
    (tmp_path / "doc.txt").write_text("not an image")
    (tmp_path / "ignored").mkdir()
    result = list_images(str(tmp_path))
    assert result["count"] == 0


def test_list_images_skips_hidden_files(tmp_path, sample_image):
    hidden = sample_image.with_name(".hidden.png")
    hidden.write_bytes(sample_image.read_bytes())
    result = list_images(str(sample_image.parent))
    names = {Path(e["path"]).name for e in result["images"]}
    assert ".hidden.png" not in names


def test_list_images_recursive_walks_subdirs(tmp_path, sample_image):
    sub = tmp_path / "sub"
    sub.mkdir()
    nested = sub / "nested.png"
    nested.write_bytes(sample_image.read_bytes())
    result = list_images(str(tmp_path), recursive=True)
    found = [Path(e["path"]).name for e in result["images"]]
    assert "nested.png" in found


def test_list_images_raises_for_missing_folder():
    with pytest.raises(ValueError):
        list_images("does/not/exist")


# ---------------------------------------------------------------------------
# Tool — read_image_metadata
# ---------------------------------------------------------------------------


def test_read_image_metadata_reports_dimensions_and_format(sample_image):
    result = read_image_metadata(str(sample_image))
    assert result["width"] == 48
    assert result["height"] == 32
    assert result["format"] == "PNG"


def test_read_image_metadata_includes_xmp_field_even_without_sidecar(sample_image):
    """A loaded image without a sidecar should still report xmp —
    either as an empty XmpData snapshot or ``None``. Either way the
    key must be present so callers don't have to special-case its
    absence."""
    result = read_image_metadata(str(sample_image))
    assert "xmp" in result


def test_read_image_metadata_raises_for_missing_file():
    with pytest.raises(ValueError):
        read_image_metadata("no/such/file.png")


# ---------------------------------------------------------------------------
# Tool — read_xmp_tags
# ---------------------------------------------------------------------------


def test_read_xmp_tags_empty_for_new_image(sample_image):
    result = read_xmp_tags(str(sample_image))
    assert result["rating"] == 0
    assert result["keywords"] == []
    assert result["is_empty"] is True


# ---------------------------------------------------------------------------
# Tool — convert_format
# ---------------------------------------------------------------------------


def test_convert_format_writes_jpeg(sample_image, tmp_path):
    dst = tmp_path / "out.jpg"
    result = convert_format(str(sample_image), str(dst), quality=85)
    assert dst.exists()
    assert result["size_bytes"] > 0
    from PIL import Image
    with Image.open(dst) as img:
        assert img.format == "JPEG"
        assert img.size == (48, 32)


def test_convert_format_rgba_to_jpeg_drops_alpha(sample_rgba_image, tmp_path):
    """JPEG can't carry alpha — we silently convert to RGB so the
    call doesn't error out on a PNG-with-alpha input."""
    dst = tmp_path / "out.jpg"
    convert_format(str(sample_rgba_image), str(dst))
    from PIL import Image
    with Image.open(dst) as img:
        assert img.mode == "RGB"


def test_convert_format_rejects_unsupported_destination(sample_image, tmp_path):
    with pytest.raises(ValueError):
        convert_format(str(sample_image), str(tmp_path / "out.xyz"))


def test_convert_format_raises_for_missing_destination_parent(sample_image, tmp_path):
    with pytest.raises(ValueError):
        convert_format(
            str(sample_image), str(tmp_path / "no_dir" / "out.png"),
        )


# ---------------------------------------------------------------------------
# Tool — puppet_from_png / puppet_inspect
# ---------------------------------------------------------------------------


def test_puppet_from_png_writes_archive_and_returns_summary(sample_rgba_image, tmp_path):
    dst = tmp_path / "rig.puppet"
    result = puppet_from_png(str(sample_rgba_image), str(dst), cell_size=10)
    assert dst.exists()
    assert result["vertex_count"] > 0
    assert result["triangle_count"] > 0
    assert result["parameter_count"] > 20   # standard params seeded


def test_puppet_inspect_returns_inventory(sample_rgba_image, tmp_path):
    dst = tmp_path / "rig.puppet"
    puppet_from_png(str(sample_rgba_image), str(dst), cell_size=10)
    inventory = puppet_inspect(str(dst))
    assert inventory["size"][0] == 20
    assert "main" in inventory["drawables"]
    assert {"id", "min", "max", "default", "key_count"} == set(
        inventory["parameters"][0],
    )
