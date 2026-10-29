"""JSON-RPC envelopes and MCP result wrappers for the MCP server.

Pure helpers shared by the dispatcher (:mod:`Imervue.mcp_server.server`),
the method handlers (:mod:`Imervue.mcp_server.server_methods`) and the stdio
loop (:mod:`Imervue.mcp_server.server_transport`): the protocol constants,
success / error envelopes, the ``tools/list`` descriptor, the ``tools/call``
``content`` envelope and the in-band protocol error.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Imervue.mcp_server.server import Tool

PROTOCOL_VERSION: str = "2025-03-26"
_PARAMS_NOT_OBJECT = "params must be an object"
SERVER_NAME: str = "imervue"
SERVER_VERSION: str = "1.0.0"


def _required_uri(params: dict) -> str:
    if not isinstance(params, dict):
        raise _MCPError(-32602, _PARAMS_NOT_OBJECT)
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri:
        raise _MCPError(-32602, "params.uri must be a non-empty string")
    return uri


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------


def _success(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error_response(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0", "id": msg_id,
        "error": {"code": code, "message": message},
    }


def _tool_descriptor(tool: Tool) -> dict[str, Any]:
    """Render one tool for ``tools/list``, including the MCP 2025-11-25
    ``outputSchema`` and ``annotations`` fields when the tool declares them."""
    descriptor: dict[str, Any] = {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
    }
    if tool.output_schema is not None:
        descriptor["outputSchema"] = tool.output_schema
    if tool.annotations is not None:
        descriptor["annotations"] = tool.annotations
    return descriptor


def _tool_success(value: Any) -> dict[str, Any]:
    """Wrap a tool's return value in the MCP ``content`` envelope.

    Strings come through as ``text``; everything else is JSON-encoded
    so the client can parse the structured payload back. Dict results are
    additionally surfaced as ``structuredContent`` so clients can consume
    the typed payload directly (validated against the tool's outputSchema)
    without re-parsing the text block."""
    if isinstance(value, str):
        return {"content": [{"type": "text", "text": value}], "isError": False}
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": text}], "isError": False,
    }
    if isinstance(value, dict):
        result["structuredContent"] = value
    return result


def _tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"Error: {message}"}],
        "isError": True,
    }


class _MCPError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
