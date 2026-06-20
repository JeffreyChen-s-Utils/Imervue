"""MCP logging utility — RFC 5424 severity levels and emit filtering.

The server lets a client set a minimum level via ``logging/setLevel`` and then
pushes ``notifications/message`` log entries at or above that level. The level
ranking and the "should this message be emitted?" decision are pure functions
here; the server holds the current level and routes emits through its
lock-serialised Notifier. Per the spec, log messages MUST NOT carry secrets or
PII — callers are responsible for what they put in ``data``.
"""
from __future__ import annotations

from typing import Any

# RFC 5424 severities, lowest → highest.
_RANK: dict[str, int] = {
    "debug": 0, "info": 1, "notice": 2, "warning": 3,
    "error": 4, "critical": 5, "alert": 6, "emergency": 7,
}
DEFAULT_LEVEL = "info"
LEVELS = tuple(_RANK)


def is_valid_level(level: Any) -> bool:
    """True when *level* is a known RFC 5424 severity name."""
    return isinstance(level, str) and level in _RANK


def should_emit(message_level: str, current_level: str) -> bool:
    """True when a message at *message_level* clears the *current_level* floor."""
    return _RANK.get(message_level, -1) >= _RANK.get(current_level, _RANK[DEFAULT_LEVEL])


def build_message(level: str, data: Any, logger: str | None = None) -> dict[str, Any]:
    """Build the ``notifications/message`` params payload."""
    params: dict[str, Any] = {"level": level, "data": data}
    if logger:
        params["logger"] = logger
    return params
