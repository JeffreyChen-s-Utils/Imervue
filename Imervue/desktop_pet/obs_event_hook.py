"""OBS WebSocket → desktop-pet event hook.

When the user is streaming / recording, the desktop pet reacts:
recording starts → pet plays a ``Record`` motion, scene changes →
``Scene`` motion, stream starts / stops → ``Stream`` motion. Same
group-name convention the other hooks (Drag, Land, Drop) use, so
the pet animator just authors more Cubism groups and the wiring is
automatic.

``obs-websocket-py`` provides the protocol client; we treat it as
an optional dependency exactly like ``pynput`` / ``sounddevice``.
Missing or unreachable OBS surfaces as :meth:`ObsEventClient.start`
returning ``False`` so the workspace can show a "needs obs-websocket-py"
or "couldn't connect" message rather than crashing the pet.

The pure helper :func:`obs_event_to_group` is the dispatch policy
in one place: an OBS event-type string in, a motion-group name out
(or ``None`` if no group matches). Lets us unit-test the policy
without instantiating the WebSocket client.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("Imervue.desktop_pet.obs_event_hook")

OBS_GROUP_STREAM: str = "Stream"
OBS_GROUP_RECORD: str = "Record"
OBS_GROUP_SCENE: str = "Scene"

OBS_EVENT_GROUPS: tuple[str, ...] = (
    OBS_GROUP_STREAM,
    OBS_GROUP_RECORD,
    OBS_GROUP_SCENE,
)
"""Canonical motion-group names the OBS hook can dispatch to. The
rig author opts in by adding motions in these groups; rigs without
them silently no-op (same convention as the drag / land / drop
hooks)."""

DEFAULT_OBS_HOST: str = "localhost"
DEFAULT_OBS_PORT: int = 4455
"""4455 is the v5 protocol default. v4 used 4444; users on older
OBS will need to override the port in settings."""


def obs_event_to_group(event_type: str) -> str | None:
    """Map an OBS event-type string to one of the canonical motion
    groups, or ``None`` when we don't react to that event.

    Matching is substring-based and case-insensitive so the helper
    works across the v4 protocol's verbose names
    (``"RecordingStarted"``) and the v5 protocol's state-changed
    events (``"RecordStateChanged"``). Both start *and* stop variants
    map to the same group; rigs can author both motions and the
    cycler picks one when fired.

    Returns ``None`` for ``""`` and for unmatched events so the
    caller can use the return value as the "did anything happen"
    signal.
    """
    if not event_type:
        return None
    lowered = event_type.lower()
    if "stream" in lowered:
        return OBS_GROUP_STREAM
    if "record" in lowered:
        return OBS_GROUP_RECORD
    if "scene" in lowered and "transition" not in lowered:
        # Bare scene-switch events fire the Scene group; transition
        # events (which fire alongside scene-switch) are filtered
        # so the pet doesn't play twice on a single scene change.
        return OBS_GROUP_SCENE
    return None


class ObsEventClient(QObject):
    """QObject wrapping an :class:`obswebsocket.obsws` client.

    Constructed once, configured with :meth:`set_endpoint`, then
    :meth:`start` — subscribers receive :attr:`group_triggered` on
    the Qt GUI thread (obswebsocket runs its callback on a worker
    thread). :meth:`stop` releases the connection; :meth:`shutdown`
    aliases it so the lifecycle matches the other drivers.
    """

    group_triggered = Signal(str)
    """Emitted with one of :data:`OBS_EVENT_GROUPS` each time OBS
    fires an event the helper recognises."""

    connection_state_changed = Signal(bool)
    """``True`` after a successful :meth:`start`, ``False`` after
    :meth:`stop` or a connection drop. Lets the workspace mirror
    the live state into its checkbox."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._host: str = DEFAULT_OBS_HOST
        self._port: int = DEFAULT_OBS_PORT
        self._password: str = ""
        self._client = None   # obswebsocket.obsws | None

    # ---- public API ------------------------------------------------

    def set_endpoint(self, host: str, port: int, password: str) -> None:
        """Cache connection params. If a connection is live it stays
        on the *old* endpoint until the caller cycles :meth:`stop` /
        :meth:`start` — silently reconnecting on every keystroke
        in the workspace's settings boxes would thrash OBS."""
        self._host = str(host) or DEFAULT_OBS_HOST
        self._port = int(port) if port else DEFAULT_OBS_PORT
        self._password = str(password)

    def is_running(self) -> bool:
        return self._client is not None

    def start(self) -> bool:
        """Open the WebSocket and register the catch-all event hook.
        Returns ``True`` on success; ``False`` if the library is
        missing or the connection fails (wrong port / password /
        OBS not running). Idempotent — a second start on a live
        client is a no-op success."""
        if self._client is not None:
            return True
        try:
            from obswebsocket import obsws
        except ImportError:
            logger.info("obs-websocket-py not installed; OBS hook unavailable")
            return False
        try:
            client = obsws(self._host, self._port, self._password)
            client.register(self._on_event)
            client.connect()
        except Exception as exc:   # noqa: BLE001 - obswebsocket raises many types
            logger.warning("OBS connect failed (%s:%s): %s",
                           self._host, self._port, exc)
            return False
        self._client = client
        self.connection_state_changed.emit(True)
        return True

    def stop(self) -> None:
        """Close the WebSocket. Safe on an already-stopped client."""
        if self._client is None:
            return
        try:
            self._client.disconnect()
        except Exception as exc:   # noqa: BLE001 - obswebsocket raises many types
            logger.warning("OBS disconnect: %s", exc)
        self._client = None
        self.connection_state_changed.emit(False)

    def shutdown(self) -> None:
        self.stop()

    # ---- internal --------------------------------------------------

    def _on_event(self, message) -> None:
        """Callback fired on obswebsocket's worker thread. We just
        translate the event type and re-emit on the Qt-affine signal;
        the receiver lives on the GUI thread, so the slot delivery
        is queued automatically."""
        event_type = ""
        # obs-websocket-py exposes either ``getType()`` (v4 events)
        # or the raw payload via ``input`` (v5). Be defensive: the
        # library version may change and our hook is the path of
        # least intrusion when OBS evolves.
        if hasattr(message, "getType"):
            try:
                event_type = str(message.getType())
            except Exception:   # noqa: BLE001 - tolerate malformed events
                event_type = ""
        if not event_type and hasattr(message, "input"):
            try:
                event_type = str(message.input.get("eventType", ""))
            except Exception:   # noqa: BLE001 - tolerate malformed events
                event_type = ""
        group = obs_event_to_group(event_type)
        if group is not None:
            self.group_triggered.emit(group)
