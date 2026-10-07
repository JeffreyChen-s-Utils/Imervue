"""Thread-safe observed plugin/resource availability without speculative capability probes."""
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock

STATES = frozenset({"available", "loaded", "checking", "missing", "downloading", "running",
                    "failed", "cancelling", "cancelled", "installed", "unloaded"})


@dataclass(frozen=True)
class PluginStatus:
    """An observed component outcome; loaded does not promise optional models are ready."""
    key: str
    name: str
    status: str
    reason: str = ""
    scope: str = "global"


class StatusRegistry:
    """Keep the latest state per component without retaining windows or plugin instances."""
    def __init__(self) -> None:
        self._lock = RLock()
        self._rows: dict[str, PluginStatus] = {}

    def publish(self, key: str, name: str, status: str, reason: str = "", *,
                scope: str = "global") -> None:
        """Replace one observed state; workers may call this without touching Qt."""
        if status not in STATES:
            raise ValueError(f"Unknown plugin state: {status}")
        with self._lock:
            self._rows[key] = PluginStatus(key, name, status, reason, scope)

    def snapshot(self, scope: str | None = None) -> tuple[PluginStatus, ...]:
        """Return immutable states; a window includes its own load results and shared resources."""
        with self._lock:
            return tuple(row for row in self._rows.values()
                         if scope is None or row.scope in {scope, "global"})

    def clear(self, scope: str) -> None:
        """Release only a closing/reloaded window's load outcomes."""
        with self._lock:
            self._rows = {key: row for key, row in self._rows.items() if row.scope != scope}


status_registry = StatusRegistry()
