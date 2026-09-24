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

    No origin (native clients), ``null`` or ``file://`` (pages opened from
    disk), a localhost web origin (a tool served locally) and non-web schemes
    are allowed. A web page on any other ``http(s)`` host is refused.
    """
    if not origin or origin == "null":
        return True
    parts = urlsplit(origin)
    if parts.scheme.lower() not in ("http", "https"):
        return True
    return (parts.hostname or "").lower() in _LOCAL_HOSTS
