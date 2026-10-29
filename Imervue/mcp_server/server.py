"""MCP protocol loop — JSON-RPC 2.0 over stdio.

Implements the subset of the Model Context Protocol used by Claude
Code, Claude Desktop and other MCP clients:

* ``initialize`` — handshake; advertise capabilities and server info.
* ``tools/list`` — enumerate available tools with their JSON-Schema
  input definitions.
* ``tools/call`` — invoke a tool with caller-supplied arguments and
  return the result wrapped in the protocol's ``content`` envelope.
* ``notifications/*`` — silently accepted (no response).

No external dependency on the ``mcp`` SDK — the protocol surface
covered here is small enough to implement directly, which keeps the
server importable in any environment that already runs Imervue.

Tool registry is built once at module import via
:func:`Imervue.mcp_server.tools.register_default_tools`; tests can
construct a fresh :class:`MCPServer` and register a different set if
they need to.

This module is the public import location: it owns the tool registry, the
dispatcher and ``_METHOD_HANDLERS`` (the registered method names), and
re-exports the rest — the ``_on_*`` handlers live in ``server_methods``, the
envelopes and protocol constants in ``server_jsonrpc`` and the stdio loop
with its resource watcher in ``server_transport``.
"""
from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from Imervue.mcp_server.server_jsonrpc import (
    _PARAMS_NOT_OBJECT,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    _error_response,
    _MCPError,
    _required_uri,
    _success,
    _tool_descriptor,
    _tool_error,
    _tool_success,
)
from Imervue.mcp_server.server_methods import MethodHandlersMixin
from Imervue.mcp_server.server_transport import _force_utf8, _start_resource_watcher, run

__all__ = [
    "PROTOCOL_VERSION",
    "SERVER_NAME",
    "SERVER_VERSION",
    "_METHOD_HANDLERS",
    "_PARAMS_NOT_OBJECT",
    "MCPServer",
    "Tool",
    "_MCPError",
    "_error_response",
    "_force_utf8",
    "_required_uri",
    "_start_resource_watcher",
    "_success",
    "_tool_descriptor",
    "_tool_error",
    "_tool_success",
    "run",
]

logger = logging.getLogger("Imervue.mcp_server")


@dataclass
class Tool:
    """One MCP tool definition + its handler."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None
    accepts_progress: bool = False


@dataclass
class MCPServer(MethodHandlersMixin):
    """In-memory tool registry plus a JSON-RPC dispatcher.

    The server doesn't hold transport state — pass each inbound
    message to :meth:`handle_message` and forward its return value to
    the client. ``None`` means "this was a notification, no reply
    expected"."""

    tools: dict[str, Tool] = field(default_factory=dict)
    resource_root: str | None = None
    notifier: Any = None  # Notifier | None — set when push notifications are wired
    subscriptions: Any = field(default=None)  # SubscriptionRegistry | None
    log_level: str = "info"

    def __post_init__(self) -> None:
        if self.subscriptions is None:
            from Imervue.mcp_server.notifications import SubscriptionRegistry
            self.subscriptions = SubscriptionRegistry()

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
        output_schema: dict[str, Any] | None = None,
        annotations: dict[str, Any] | None = None,
    ) -> None:
        if name in self.tools:
            raise ValueError(f"tool {name!r} already registered")
        self.tools[name] = Tool(
            name=name, description=description,
            input_schema=input_schema, handler=handler,
            output_schema=output_schema, annotations=annotations,
            accepts_progress="progress" in inspect.signature(handler).parameters,
        )

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Dispatch a single inbound JSON-RPC message. Returns the
        response dict, or ``None`` for notifications."""
        if not isinstance(message, dict):
            return _error_response(None, -32600, "request must be a JSON object")
        method = message.get("method")
        if not isinstance(method, str):
            return _error_response(message.get("id"), -32600, "missing 'method'")
        if method.startswith("notifications/"):
            return None
        msg_id = message.get("id")
        params = message.get("params") or {}
        handler = _METHOD_HANDLERS.get(method)
        if handler is None:
            return _error_response(msg_id, -32601, f"unknown method {method!r}")
        try:
            return handler(self, msg_id, params)
        except _MCPError as exc:
            return _error_response(msg_id, exc.code, exc.message)
        except Exception as exc:   # protocol must never crash
            logger.exception("MCP handler crashed: %s", exc)
            return _error_response(msg_id, -32603, f"internal error: {exc}")

    # ---- server-pushed notifications ---------------------------------

    def notify_resource_updated(self, uri: str) -> None:
        """Push ``notifications/resources/updated`` if *uri* is subscribed."""
        if self.notifier is not None and self.subscriptions.is_subscribed(uri):
            self.notifier.notify("notifications/resources/updated", {"uri": uri})

    def notify_list_changed(self) -> None:
        """Push ``notifications/resources/list_changed`` to the client."""
        if self.notifier is not None:
            self.notifier.notify("notifications/resources/list_changed")

    def emit_log(self, level: str, data: Any, logger_name: str | None = None) -> None:
        """Push a ``notifications/message`` if *level* clears the current floor.

        ``data`` must not contain secrets or PII (per the MCP spec) — that is
        the caller's responsibility.
        """
        from Imervue.mcp_server.logging import build_message, should_emit
        if self.notifier is not None and should_emit(level, self.log_level):
            self.notifier.notify("notifications/message", build_message(level, data, logger_name))

    def _with_progress(
        self, tool: Tool, args: dict, params: dict,
    ) -> dict[str, Any]:
        """Inject a ProgressReporter for tools that declare a ``progress`` param.

        The reporter is bound to the request's ``_meta.progressToken`` (if any)
        and the server's notifier, so it no-ops when the client didn't ask for
        progress or no stream is wired."""
        if not tool.accepts_progress:
            return args
        from Imervue.mcp_server.progress import ProgressReporter, progress_token
        reporter = ProgressReporter(self.notifier, progress_token(params))
        return {**args, "progress": reporter}


_METHOD_HANDLERS: dict[str, Callable[[MCPServer, Any, dict], dict]] = {
    "initialize": MCPServer._on_initialize,
    "tools/list": MCPServer._on_tools_list,
    "tools/call": MCPServer._on_tools_call,
    "prompts/list": MCPServer._on_prompts_list,
    "prompts/get": MCPServer._on_prompts_get,
    "resources/list": MCPServer._on_resources_list,
    "resources/templates/list": MCPServer._on_resources_templates_list,
    "resources/read": MCPServer._on_resources_read,
    "ping": MCPServer._on_ping,
    "completion/complete": MCPServer._on_completion_complete,
    "resources/subscribe": MCPServer._on_resources_subscribe,
    "resources/unsubscribe": MCPServer._on_resources_unsubscribe,
    "logging/setLevel": MCPServer._on_logging_set_level,
}
