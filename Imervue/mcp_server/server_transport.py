"""stdio transport of the MCP server.

:func:`run` reads newline-delimited JSON-RPC messages, hands each one to an
:class:`~Imervue.mcp_server.server.MCPServer` and writes the replies through
the same locked :class:`~Imervue.mcp_server.notifications.Notifier` that the
resource watcher pushes notifications with. ``MCPServer`` is imported at call
time so this module and ``server`` (which re-exports :func:`run`) never import
each other at load time.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import TYPE_CHECKING, TextIO

from Imervue.mcp_server.server_jsonrpc import _error_response

if TYPE_CHECKING:
    from Imervue.mcp_server.server import MCPServer

logger = logging.getLogger("Imervue.mcp_server")


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------


def _force_utf8(stream: TextIO | None) -> None:
    """Reconfigure a real stdio pipe to UTF-8.

    On Windows a piped stdio stream defaults to the ANSI code page (e.g.
    cp950); combined with ``ensure_ascii=False`` when serialising responses,
    a tool result containing an emoji or out-of-code-page CJK character would
    raise ``UnicodeEncodeError`` mid-write and kill the server. Injected test
    streams (``StringIO``) are already text-clean and expose no
    ``reconfigure``, so this is a no-op for them.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


def run(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Block on stdin reading newline-delimited JSON-RPC messages and
    write responses to stdout. Returns when stdin reaches EOF.

    ``stdin`` / ``stdout`` default to the system handles but can be
    swapped for in-memory ``io.StringIO`` objects in tests."""
    from Imervue.mcp_server.notifications import Notifier
    from Imervue.mcp_server.server import MCPServer
    server = MCPServer(resource_root=os.environ.get("IMERVUE_MCP_ROOT"))
    from Imervue.mcp_server.tools import register_default_tools
    register_default_tools(server)
    if stdin is None:
        _force_utf8(sys.stdin)
    if stdout is None:
        _force_utf8(sys.stdout)
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
