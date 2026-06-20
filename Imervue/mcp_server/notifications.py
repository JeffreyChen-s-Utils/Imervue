"""Server-pushed MCP notifications over a synchronous stdio loop.

A synchronous newline-delimited JSON-RPC server can still push notifications
(messages with no ``id``) as long as every write to stdout is serialised. The
:class:`Notifier` wraps the output stream behind a lock so the main read loop
and any background thread (a watchdog file watcher) can both emit lines without
interleaving. Notifications are fire-and-forget — no response is expected.

The subscription bookkeeping (:class:`SubscriptionRegistry`) is pure and
unit-testable without a live stream or filesystem.
"""
from __future__ import annotations

import json
import threading
from typing import Any, TextIO


class Notifier:
    """Serialise JSON-RPC notification writes to a stream behind a lock."""

    def __init__(self, stream: TextIO):
        self._stream = stream
        self._lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        """Write any pre-built JSON-RPC message (response or notification).

        Shared by the main read loop (responses, with an ``id``) and background
        threads (notifications, no ``id``) so writes never interleave.
        """
        line = json.dumps(message, ensure_ascii=False) + "\n"
        with self._lock:
            self._stream.write(line)
            self._stream.flush()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Write a single ``{method[, params]}`` notification (no ``id``)."""
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)


class SubscriptionRegistry:
    """Thread-safe set of subscribed resource URIs."""

    def __init__(self) -> None:
        self._uris: set[str] = set()
        self._lock = threading.Lock()

    def subscribe(self, uri: str) -> None:
        with self._lock:
            self._uris.add(uri)

    def unsubscribe(self, uri: str) -> None:
        with self._lock:
            self._uris.discard(uri)

    def is_subscribed(self, uri: str) -> bool:
        with self._lock:
            return uri in self._uris

    def snapshot(self) -> set[str]:
        with self._lock:
            return set(self._uris)
