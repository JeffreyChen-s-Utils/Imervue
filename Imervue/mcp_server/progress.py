"""MCP progress notifications for long-running tool calls.

Per the MCP progress utility, a client opts in by putting a ``progressToken``
in a request's ``params._meta``; the server then pushes
``notifications/progress`` messages referencing that token while the tool
runs. Progress is a shared utility, not a declared capability — the client
signals interest purely by sending the token.

:class:`ProgressReporter` is the server-side sender. It no-ops when no token
or notifier is wired (e.g. a stdio-less unit test or a client that didn't ask
for progress) and enforces the spec's monotonically-increasing ``progress``
rule, so a handler can call :meth:`report` freely without guarding.
"""
from __future__ import annotations

from typing import Any

_PROGRESS_METHOD = "notifications/progress"


class ProgressReporter:
    """Send ``notifications/progress`` for one tool call, or no-op."""

    def __init__(self, notifier: Any, token: str | int | None):
        self._notifier = notifier
        self._token = token
        self._last = -1.0

    @property
    def active(self) -> bool:
        """True when a token and a notifier are both present."""
        return self._notifier is not None and self._token is not None

    def report(
        self,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        """Push one progress update, dropping non-increasing values.

        The spec requires ``progress`` to strictly increase across a token's
        notifications, so a value at or below the last one sent is ignored
        rather than emitted out of order.
        """
        if not self.active:
            return
        value = float(progress)
        if value <= self._last:
            return
        self._last = value
        params: dict[str, Any] = {"progressToken": self._token, "progress": value}
        if total is not None:
            params["total"] = float(total)
        if message is not None:
            params["message"] = str(message)
        self._notifier.notify(_PROGRESS_METHOD, params)


def progress_token(params: dict[str, Any]) -> str | int | None:
    """Extract a request's ``_meta.progressToken`` (a string or int), or None."""
    meta = params.get("_meta")
    token = meta.get("progressToken") if isinstance(meta, dict) else None
    if isinstance(token, bool) or not isinstance(token, (str, int)):
        return None
    return token
