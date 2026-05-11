"""VTube Studio Public API server (minimal subset).

Speaks the JSON-over-WebSocket protocol that third-party trackers
(iPhone iFacialMocap, MacBook camera apps, fan-made keyboard rigs)
use to drive a Live2D avatar. When this server is enabled, any of
those tools can connect to ``ws://127.0.0.1:8001`` and start
injecting parameter values — the same wire the real VTube Studio
app exposes.

Scope is deliberately small. We handle the message types needed to
get a tracker from "connect" to "InjectParameterDataRequest":

* ``APIStateRequest`` — capability probe
* ``AuthenticationTokenRequest`` — auto-issue a token
* ``AuthenticationRequest`` — auto-accept any submitted token
* ``CurrentModelRequest`` — minimal model info
* ``Live2DParameterListRequest`` — list document parameters
* ``ParameterValueRequest`` — read one parameter
* ``ParameterCreationRequest`` — register a new parameter
* ``InjectParameterDataRequest`` — write parameter values

Everything else returns a polite error envelope rather than crashing
the connection. The Qt half (``VTubeStudioServer``) is optional — it
imports ``QtWebSockets`` lazily so test environments without the
module still exercise the protocol handler.

Security: the server binds ``127.0.0.1`` only (never ``0.0.0.0``).
The auto-issued token grants full parameter-write access — this is
a developer puppet plugin, not a public service.
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.vts_api")

DEFAULT_VTS_PORT: int = 8001
LOCALHOST: str = "127.0.0.1"
API_NAME: str = "VTubeStudioPublicAPI"
API_VERSION: str = "1.0"


class VTubeStudioHandler:
    """Pure-Python state machine for one VTS client session.

    Owns the issued auth token (per-session — we don't persist it),
    routes requests to the right handler, and writes responses back
    as Python dicts that the Qt wrapper serialises. Kept Qt-free so
    tests can verify the protocol without a WebSocket."""

    def __init__(self, canvas: PuppetCanvas):
        self._canvas = canvas
        self._issued_token: str | None = None
        self._authenticated: bool = False

    def is_authenticated(self) -> bool:
        return self._authenticated

    def handle_message(self, message: dict) -> dict:
        """Dispatch one inbound request and return the response dict.

        Always emits an envelope — even on error paths — so the
        client never sees a torn message. The ``timestamp`` field
        is filled with the current wall time in milliseconds (VTS
        clients use it for round-trip latency calculations)."""
        if not isinstance(message, dict):
            return self._error_envelope("", "InvalidRequest", "message must be a JSON object")
        request_id = str(message.get("requestID", ""))
        message_type = message.get("messageType")
        data = message.get("data") or {}
        handler = _MESSAGE_HANDLERS.get(message_type)
        if handler is None:
            return self._envelope(
                request_id, "APIError",
                {"errorID": 1, "message": f"unknown messageType {message_type!r}"},
            )
        response_type, response_data = handler(self, data)
        return self._envelope(request_id, response_type, response_data)

    # ---- handlers ------------------------------------------------------

    def _on_api_state(self, _data: dict) -> tuple[str, dict]:
        return "APIStateResponse", {
            "active": True,
            "vTubeStudioVersion": API_VERSION,
            "currentSessionAuthenticated": self._authenticated,
        }

    def _on_auth_token(self, data: dict) -> tuple[str, dict]:
        plugin_name = str(data.get("pluginName", ""))
        plugin_dev = str(data.get("pluginDeveloper", ""))
        # Auto-issue. Tokens are 32 bytes of urlsafe randomness — well
        # over the entropy required for a session id. We don't persist
        # across server restarts; the next connection re-authenticates.
        token = secrets.token_urlsafe(32)
        self._issued_token = token
        logger.info("VTS auth token issued to %s / %s", plugin_name, plugin_dev)
        return "AuthenticationTokenResponse", {"authenticationToken": token}

    def _on_auth(self, data: dict) -> tuple[str, dict]:
        token = data.get("authenticationToken")
        if not isinstance(token, str) or token != self._issued_token:
            return "AuthenticationResponse", {
                "authenticated": False,
                "reason": "unknown token — request AuthenticationTokenRequest first",
            }
        self._authenticated = True
        return "AuthenticationResponse", {"authenticated": True, "reason": "ok"}

    def _on_current_model(self, _data: dict) -> tuple[str, dict]:
        doc = self._canvas.document()
        return "CurrentModelResponse", {
            "modelLoaded": doc is not None,
            "modelName": "puppet" if doc is not None else "",
            "modelID": "",
            "vtsModelName": "",
            "vtsModelIconName": "",
            "live2DModelName": "puppet" if doc is not None else "",
            "modelLoadTime": int(time.time() * 1000),
        }

    def _on_parameter_list(self, _data: dict) -> tuple[str, dict]:
        doc = self._canvas.document()
        if doc is None:
            return "Live2DParameterListResponse", {"parameters": []}
        values = self._canvas.parameter_values()
        parameters = [
            {
                "name": p.id,
                "value": float(values.get(p.id, p.default)),
                "min": float(p.min),
                "max": float(p.max),
                "defaultValue": float(p.default),
            }
            for p in doc.parameters
        ]
        return "Live2DParameterListResponse", {"parameters": parameters}

    def _on_parameter_value(self, data: dict) -> tuple[str, dict]:
        if not self._require_auth():
            return "APIError", {"errorID": 50, "message": "not authenticated"}
        name = str(data.get("name", ""))
        doc = self._canvas.document()
        param = doc.parameter(name) if doc is not None else None
        if param is None:
            return "APIError", {"errorID": 2, "message": f"unknown parameter {name!r}"}
        value = float(self._canvas.parameter_values().get(name, param.default))
        return "ParameterValueResponse", {
            "name": name,
            "value": value,
            "min": param.min,
            "max": param.max,
            "defaultValue": param.default,
        }

    def _on_parameter_creation(self, data: dict) -> tuple[str, dict]:
        if not self._require_auth():
            return "APIError", {"errorID": 50, "message": "not authenticated"}
        from puppet.operations import add_parameter
        doc = self._canvas.document()
        if doc is None:
            return "APIError", {"errorID": 3, "message": "no document loaded"}
        name = str(data.get("parameterName", ""))
        if not name:
            return "APIError", {"errorID": 4, "message": "parameterName required"}
        try:
            ok = add_parameter(
                doc, name,
                min_value=float(data.get("min", -1.0)),
                max_value=float(data.get("max", 1.0)),
                default=float(data.get("defaultValue", 0.0)),
            )
        except ValueError as exc:
            return "APIError", {"errorID": 5, "message": str(exc)}
        if not ok:
            return "APIError", {"errorID": 6, "message": "parameter already exists"}
        self._canvas.load_document(doc)
        return "ParameterCreationResponse", {"parameterName": name}

    def _on_inject(self, data: dict) -> tuple[str, dict]:
        """The big one — third-party trackers call this every frame to
        push the latest parameter values into our puppet."""
        if not self._require_auth():
            return "APIError", {"errorID": 50, "message": "not authenticated"}
        values = data.get("parameterValues") or []
        applied = 0
        for entry in values:
            if not isinstance(entry, dict):
                continue
            param_id = entry.get("id") or entry.get("name")
            if not isinstance(param_id, str):
                continue
            try:
                value = float(entry.get("value", 0.0))
            except (TypeError, ValueError):
                continue
            self._canvas.set_parameter_value(param_id, value)
            applied += 1
        return "InjectParameterDataResponse", {"parameterValuesApplied": applied}

    # ---- helpers -------------------------------------------------------

    def _require_auth(self) -> bool:
        return self._authenticated

    def _envelope(
        self, request_id: str, message_type: str, data: dict,
    ) -> dict:
        return {
            "apiName": API_NAME,
            "apiVersion": API_VERSION,
            "timestamp": int(time.time() * 1000),
            "requestID": request_id,
            "messageType": message_type,
            "data": data,
        }

    def _error_envelope(
        self, request_id: str, error_kind: str, reason: str,
    ) -> dict:
        return self._envelope(
            request_id, "APIError",
            {"errorID": 1, "message": f"{error_kind}: {reason}"},
        )


_MESSAGE_HANDLERS = {
    "APIStateRequest": VTubeStudioHandler._on_api_state,
    "AuthenticationTokenRequest": VTubeStudioHandler._on_auth_token,
    "AuthenticationRequest": VTubeStudioHandler._on_auth,
    "CurrentModelRequest": VTubeStudioHandler._on_current_model,
    "Live2DParameterListRequest": VTubeStudioHandler._on_parameter_list,
    "ParameterValueRequest": VTubeStudioHandler._on_parameter_value,
    "ParameterCreationRequest": VTubeStudioHandler._on_parameter_creation,
    "InjectParameterDataRequest": VTubeStudioHandler._on_inject,
}


# ---------------------------------------------------------------------------
# Qt wrapper
# ---------------------------------------------------------------------------


class VTubeStudioServer(QObject):
    """Qt WebSocket server that funnels client messages through one
    :class:`VTubeStudioHandler` per session.

    QtWebSockets is imported lazily so a missing module just makes
    ``set_enabled(True)`` return ``False`` instead of crashing on
    import. The workspace toggles the server on a toolbar action."""

    state_changed = Signal()

    def __init__(self, canvas: PuppetCanvas, parent=None,
                 *, port: int = DEFAULT_VTS_PORT):
        super().__init__(parent)
        self._canvas = canvas
        self._port = int(port)
        self._enabled = False
        self._server = None
        self._sessions: dict = {}

    def is_enabled(self) -> bool:
        return self._enabled

    def port(self) -> int:
        return self._port

    def set_enabled(self, enabled: bool) -> bool:
        if enabled == self._enabled:
            return True
        if enabled:
            ok = self._start()
            if not ok:
                self._enabled = False
                self.state_changed.emit()
                return False
        else:
            self._stop()
        self._enabled = bool(enabled)
        self.state_changed.emit()
        return True

    def shutdown(self) -> None:
        self._stop()

    def _start(self) -> bool:  # pragma: no cover - needs QtWebSockets + network
        try:
            from PySide6.QtNetwork import QHostAddress
            from PySide6.QtWebSockets import QWebSocketServer
        except ImportError:
            logger.info("QtWebSockets not available; VTS API disabled")
            return False
        server = QWebSocketServer(
            "puppet-vts", QWebSocketServer.SslMode.NonSecureMode, self,
        )
        # 127.0.0.1 only — never 0.0.0.0. Third-party trackers run on
        # the same machine; exposing this on the network would let
        # anyone on the LAN drive the puppet.
        if not server.listen(QHostAddress(LOCALHOST), self._port):
            logger.warning(
                "VTS API failed to listen on %s:%d", LOCALHOST, self._port,
            )
            return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        logger.info("VTS API listening on %s:%d", LOCALHOST, self._port)
        return True

    def _stop(self) -> None:  # pragma: no cover - needs QtWebSockets
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        for socket in list(self._sessions):
            try:
                socket.close()
            except RuntimeError:
                pass
        self._sessions.clear()

    def _on_new_connection(self) -> None:  # pragma: no cover - needs network
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            handler = VTubeStudioHandler(self._canvas)
            self._sessions[socket] = handler
            socket.textMessageReceived.connect(
                lambda text, s=socket: self._on_text(s, text),
            )
            socket.disconnected.connect(lambda s=socket: self._on_disconnect(s))

    def _on_text(self, socket, text: str) -> None:  # pragma: no cover - needs network
        handler = self._sessions.get(socket)
        if handler is None:
            return
        try:
            message = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.debug("VTS bad JSON from client: %s", exc)
            return
        response = handler.handle_message(message)
        socket.sendTextMessage(json.dumps(response))

    def _on_disconnect(self, socket) -> None:  # pragma: no cover - needs network
        self._sessions.pop(socket, None)
        try:
            socket.deleteLater()
        except RuntimeError:
            pass
