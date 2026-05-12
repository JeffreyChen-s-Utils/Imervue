"""Imervue MCP (Model Context Protocol) server.

Exposes a subset of Imervue's pure-logic helpers — image metadata,
XMP tags, format conversion, puppet rig inspection — to any MCP
client (Claude Code, Claude Desktop, Cursor, Cline, etc.) over the
stdio transport.

The server is deliberately Qt-free so it can run as a subprocess in
headless environments. Run with::

    python -m Imervue.mcp_server

Project-level Claude Code wiring lives in ``.mcp.json`` at the repo
root; per-user Claude Desktop wiring is documented in
``docs/en/mcp_server.rst``.
"""

from Imervue.mcp_server.server import MCPServer, run

__all__ = ["MCPServer", "run"]
