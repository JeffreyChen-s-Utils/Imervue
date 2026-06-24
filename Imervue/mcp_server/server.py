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
"""
from __future__ import annotations

import inspect
import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TextIO

logger = logging.getLogger("Imervue.mcp_server")

PROTOCOL_VERSION: str = "2025-03-26"
SERVER_NAME: str = "imervue"
SERVER_VERSION: str = "1.0.0"


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
class MCPServer:
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
        except Exception as exc:   # noqa: BLE001 - protocol must never crash
            logger.exception("MCP handler crashed: %s", exc)
            return _error_response(msg_id, -32603, f"internal error: {exc}")

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
            raise _MCPError(-32602, "params must be an object")
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
            raise _MCPError(-32602, "params must be an object")
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

    # ---- server-pushed notifications ---------------------------------

    def notify_resource_updated(self, uri: str) -> None:
        """Push ``notifications/resources/updated`` if *uri* is subscribed."""
        if self.notifier is not None and self.subscriptions.is_subscribed(uri):
            self.notifier.notify("notifications/resources/updated", {"uri": uri})

    def notify_list_changed(self) -> None:
        """Push ``notifications/resources/list_changed`` to the client."""
        if self.notifier is not None:
            self.notifier.notify("notifications/resources/list_changed")

    def _on_logging_set_level(self, msg_id: Any, params: dict) -> dict:
        from Imervue.mcp_server.logging import is_valid_level
        level = params.get("level") if isinstance(params, dict) else None
        if not is_valid_level(level):
            raise _MCPError(-32602, f"invalid log level: {level!r}")
        self.log_level = level
        return _success(msg_id, {})

    def emit_log(self, level: str, data: Any, logger_name: str | None = None) -> None:
        """Push a ``notifications/message`` if *level* clears the current floor.

        ``data`` must not contain secrets or PII (per the MCP spec) — that is
        the caller's responsibility.
        """
        from Imervue.mcp_server.logging import build_message, should_emit
        if self.notifier is not None and should_emit(level, self.log_level):
            self.notifier.notify("notifications/message", build_message(level, data, logger_name))

    def _on_prompts_list(self, msg_id: Any, _params: dict) -> dict:
        from Imervue.mcp_server.prompts import list_prompts
        return _success(msg_id, {"prompts": list_prompts()})

    def _on_prompts_get(self, msg_id: Any, params: dict) -> dict:
        if not isinstance(params, dict):
            raise _MCPError(-32602, "params must be an object")
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
            raise _MCPError(-32602, "params must be an object")
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
        except Exception as exc:   # noqa: BLE001 - tools handle their own errors
            logger.exception("tool %s crashed", name)
            return _success(msg_id, _tool_error(str(exc)))
        return _success(msg_id, _tool_success(raw_result))

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


def _required_uri(params: dict) -> str:
    if not isinstance(params, dict):
        raise _MCPError(-32602, "params must be an object")
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


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------


def run(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Block on stdin reading newline-delimited JSON-RPC messages and
    write responses to stdout. Returns when stdin reaches EOF.

    ``stdin`` / ``stdout`` default to the system handles but can be
    swapped for in-memory ``io.StringIO`` objects in tests."""
    from Imervue.mcp_server.notifications import Notifier
    server = MCPServer(resource_root=os.environ.get("IMERVUE_MCP_ROOT"))
    from Imervue.mcp_server.tools import register_default_tools
    register_default_tools(server)
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    server.notifier = Notifier(output_stream)
    watcher = _start_resource_watcher(server)
    try:
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                response = _error_response(None, -32700, f"parse error: {exc}")
            else:
                response = server.handle_message(message)
            if response is None:
                continue
            # Responses share the same locked writer as push notifications.
            server.notifier.send(response)
    finally:
        if watcher is not None:
            watcher.stop()


def _start_resource_watcher(server: MCPServer):
    """Watch the resource root and push resource notifications. None if unavailable."""
    root = server.resource_root
    if not root or not os.path.isdir(root):
        return None
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return None
    from Imervue.mcp_server.resources import image_uri

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event):  # noqa: D401 - watchdog hook
            try:
                if not getattr(event, "is_directory", False):
                    server.notify_resource_updated(image_uri(event.src_path))
                server.notify_list_changed()
            except Exception:  # noqa: BLE001 - never let a watcher error kill the loop
                logger.debug("resource watcher notify failed", exc_info=True)

    try:
        observer = Observer()
        observer.schedule(_Handler(), root, recursive=False)
        observer.daemon = True
        observer.start()
    except (OSError, RuntimeError):
        return None
    return observer


