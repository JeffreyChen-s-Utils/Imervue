"""JSON-RPC method handlers of the MCP server, as a mixin of ``MCPServer``.

Each ``_on_<method>`` answers one request: it validates ``params``, raises
:class:`~Imervue.mcp_server.server_jsonrpc._MCPError` for an in-band protocol
error and returns the success envelope otherwise. ``MCPServer`` maps method
names to these in ``server._METHOD_HANDLERS``; the mixin adds no state and
reads the server's own fields (``tools``, ``resource_root``, ``subscriptions``,
``log_level``) and its ``_with_progress``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from Imervue.mcp_server.server_jsonrpc import (
    _PARAMS_NOT_OBJECT,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    _MCPError,
    _required_uri,
    _success,
    _tool_descriptor,
    _tool_error,
    _tool_success,
)

if TYPE_CHECKING:
    from Imervue.mcp_server.notifications import SubscriptionRegistry
    from Imervue.mcp_server.server import Tool

logger = logging.getLogger("Imervue.mcp_server")


class MethodHandlersMixin:
    """The ``_on_*`` request handlers dispatched by ``MCPServer.handle_message``."""

    tools: dict[str, Tool]
    resource_root: str | None
    subscriptions: SubscriptionRegistry
    log_level: str

    # ---- method handlers ---------------------------------------------

    def _on_initialize(self, msg_id: Any, _params: dict) -> dict:
        return _success(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": False},
                "resources": {"subscribe": True, "listChanged": True},
                "completions": {},
                "logging": {},
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    def _on_ping(self, msg_id: Any, _params: dict) -> dict:
        return _success(msg_id, {})

    def _on_completion_complete(self, msg_id: Any, params: dict) -> dict:
        if not isinstance(params, dict):
            raise _MCPError(-32602, _PARAMS_NOT_OBJECT)
        from Imervue.mcp_server.completion import complete
        return _success(msg_id, complete(params.get("ref"), params.get("argument") or {}))

    def _on_resources_list(self, msg_id: Any, params: dict) -> dict:
        from Imervue.mcp_server.resources import ResourceError, list_resources
        try:
            return _success(msg_id, list_resources(self.resource_root, params.get("cursor")))
        except ResourceError as exc:
            raise _MCPError(exc.code, exc.message) from exc

    def _on_resources_templates_list(self, msg_id: Any, _params: dict) -> dict:
        from Imervue.mcp_server.resources import list_resource_templates
        return _success(msg_id, list_resource_templates())

    def _on_resources_read(self, msg_id: Any, params: dict) -> dict:
        if not isinstance(params, dict):
            raise _MCPError(-32602, _PARAMS_NOT_OBJECT)
        from Imervue.mcp_server.resources import ResourceError, read_resource
        try:
            return _success(msg_id, read_resource(params.get("uri")))
        except ResourceError as exc:
            raise _MCPError(exc.code, exc.message) from exc

    def _on_resources_subscribe(self, msg_id: Any, params: dict) -> dict:
        self.subscriptions.subscribe(_required_uri(params))
        return _success(msg_id, {})

    def _on_resources_unsubscribe(self, msg_id: Any, params: dict) -> dict:
        self.subscriptions.unsubscribe(_required_uri(params))
        return _success(msg_id, {})

    def _on_logging_set_level(self, msg_id: Any, params: dict) -> dict:
        from Imervue.mcp_server.logging import is_valid_level
        level = params.get("level") if isinstance(params, dict) else None
        if not is_valid_level(level):
            raise _MCPError(-32602, f"invalid log level: {level!r}")
        self.log_level = level
        return _success(msg_id, {})

    def _on_prompts_list(self, msg_id: Any, _params: dict) -> dict:
        from Imervue.mcp_server.prompts import list_prompts
        return _success(msg_id, {"prompts": list_prompts()})

    def _on_prompts_get(self, msg_id: Any, params: dict) -> dict:
        if not isinstance(params, dict):
            raise _MCPError(-32602, _PARAMS_NOT_OBJECT)
        name = params.get("name")
        if not isinstance(name, str):
            raise _MCPError(-32602, "params.name must be a string")
        arguments = params.get("arguments") or {}
        from Imervue.mcp_server.prompts import get_prompt
        try:
            return _success(msg_id, get_prompt(name, arguments))
        except ValueError as exc:
            raise _MCPError(-32602, str(exc)) from exc

    def _on_tools_list(self, msg_id: Any, _params: dict) -> dict:
        return _success(msg_id, {
            "tools": [_tool_descriptor(t) for t in self.tools.values()],
        })

    def _on_tools_call(self, msg_id: Any, params: dict) -> dict:
        if not isinstance(params, dict):
            raise _MCPError(-32602, _PARAMS_NOT_OBJECT)
        name = params.get("name")
        if not isinstance(name, str):
            raise _MCPError(-32602, "params.name must be a string")
        tool = self.tools.get(name)
        if tool is None:
            raise _MCPError(-32602, f"unknown tool {name!r}")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            raise _MCPError(-32602, "params.arguments must be an object")
        call_args = self._with_progress(tool, args, params)
        try:
            raw_result = tool.handler(**call_args)
        except TypeError as exc:
            # Bad argument shape — surface to client as a tool error
            # rather than a protocol error, so the client can retry.
            return _success(msg_id, _tool_error(f"argument error: {exc}"))
        except Exception as exc:   # tools handle their own errors
            logger.exception("tool %s crashed", name)
            return _success(msg_id, _tool_error(str(exc)))
        return _success(msg_id, _tool_success(raw_result))
