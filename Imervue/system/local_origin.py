"""Tell a browser page on another site apart from a local client.

The desktop pet's webhook and the puppet's VTube Studio API listen on
127.0.0.1. That keeps the LAN out but not the browser: any site the user has
open may send requests to localhost. Browsers always send an ``Origin``
header on those requests; command-line tools, Stream Deck and native trackers
do not. Servers refuse a request whose origin fails :func:`is_allowed_origin`.
"""
from __future__ import annotations

from urllib.parse import urlsplit

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_allowed_origin(origin: str | None) -> bool:
    """Whether a client with this ``Origin`` header may talk to a local server.

    Native clients without an origin, explicit ``file://`` origins, localhost
    web origins and non-web schemes are allowed. Opaque ``null`` origins are
    refused: local files and remote sandboxed pages cannot be distinguished
    from that header. Serve browser tools from localhost instead.
    """
    if not origin:
        return True
    if origin == "null" or any(char.isspace() for char in origin):
        return False
    try:
        parts = urlsplit(origin)
        host, _ = parts.hostname, parts.port
    except ValueError:
        return False
    if not parts.scheme:
        return False
    if parts.scheme.lower() not in ("http", "https"):
        return True
    return (host or "").lower() in _LOCAL_HOSTS
