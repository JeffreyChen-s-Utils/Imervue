"""Localhost HTTP webhook receiver — external tools poke the pet.

Anything that can fire an HTTP POST (a Zapier zap, a GitHub
Actions step, a Stream Deck button, your own shell scripts) can
trigger the pet by sending JSON to ``http://localhost:<port>/trigger``.
Same group-name convention the OBS / Twitch / drag-drop hooks use,
plus an optional ``speech`` string for the bubble.

Generalises the integration story: rather than baking every
third-party service in (Discord rich presence, Spotify, calendar,
…), accept a documented event format and let users wire their own
bridges with whatever automation tool they already use.

Pure helpers (:func:`parse_payload`, :func:`bearer_token`) are
Qt-free and HTTP-free so the parsing / auth policy is testable
without booting a server. The :class:`WebhookReceiver` Qt wrapper
owns the threaded ``ThreadingHTTPServer`` lifecycle and re-emits
parsed commands via signals on the GUI thread.

Security stance:

* Binds to ``127.0.0.1`` only (loopback). Bandit B104 flags
  ``0.0.0.0``; we intentionally never expose the receiver beyond
  the local machine — remote triggering is the user's job via SSH
  tunnel or reverse proxy if they want it.
* Optional bearer token auth. When set, every ``/trigger`` POST
  must carry ``Authorization: Bearer <token>``; mismatched / empty
  tokens get a 401. When the persisted token is empty, auth is
  off — fine for purely local use, recommended on shared machines.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("Imervue.desktop_pet.webhook_server")

DEFAULT_HOST: str = "127.0.0.1"
"""Bind address. Loopback only — never extended to 0.0.0.0 by the
public API, since the receiver doesn't authenticate by default."""

DEFAULT_PORT: int = 9876
"""Default listen port. Picked from the ephemeral range so it
doesn't clash with common services (3000, 8080, etc.). Users can
override via settings if 9876 conflicts with something local."""


@dataclass(frozen=True)
class WebhookCommand:
    """One parsed trigger: a motion group, a speech line, or both.
    ``group`` and ``speech`` are independently optional so the
    caller can use the receiver for "play a motion", "speak a
    line", or "do both" without separate endpoints."""

    group: str
    speech: str


def parse_payload(raw: object) -> WebhookCommand | None:
    """Validate + extract a :class:`WebhookCommand` from a decoded
    JSON object.

    Returns ``None`` when the payload is unusable: not a dict,
    both fields empty / missing, or fields with non-string types.
    A returned :class:`WebhookCommand` always has at least one
    non-empty field — never both blank — so callers don't waste
    a no-op trip through the signal pipeline.
    """
    if not isinstance(raw, dict):
        return None
    group = raw.get("group", "")
    speech = raw.get("speech", "")
    if not isinstance(group, str):
        group = ""
    if not isinstance(speech, str):
        speech = ""
    group = group.strip()
    speech = speech.strip()
    if not group and not speech:
        return None
    return WebhookCommand(group=group, speech=speech)


def bearer_token(authorization_header: str | None) -> str:
    """Pull the bearer token out of an ``Authorization: Bearer xxx``
    header. Empty string for missing / malformed headers — callers
    just compare against the expected token, so the policy "no
    header → empty match → fails the equality check" is the
    contract."""
    if not authorization_header:
        return ""
    text = authorization_header.strip()
    parts = text.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()


class _WebhookHandler(BaseHTTPRequestHandler):
    """Per-request handler. Lives only for the duration of one
    HTTP exchange — never holds state.

    The owning :class:`WebhookReceiver` is reached via the
    ``server.receiver`` attribute we set in :meth:`start`."""

    # Silence the noisy default access log; we route through our
    # own logger so users can tune verbosity uniformly. Parameter
    # names mirror ``BaseHTTPRequestHandler.log_message`` exactly
    # (``format``, ``*args``) so pylint W0221 doesn't complain
    # about a signature drift on override.
    def log_message(self, format, *args) -> None:   # noqa: A002, A003 - stdlib override signature
        del format, args

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _check_auth(self, receiver) -> bool:
        expected = receiver.token()
        if not expected:
            return True
        provided = bearer_token(self.headers.get("Authorization"))
        # Constant-time-style compare via ``==`` is acceptable here
        # because both strings are short and the loopback-only
        # binding means a remote attacker isn't in scope. Local
        # timing attacks against a desktop pet are not a credible
        # threat model.
        return provided == expected

    def do_GET(self) -> None:   # noqa: N802 - stdlib override
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:   # noqa: N802 - stdlib override
        receiver = getattr(self.server, "receiver", None)
        if receiver is None or self.path != "/trigger":
            self._send_json(404, {"error": "not found"})
            return
        if not self._check_auth(receiver):
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 64_000:
            self._send_json(400, {"error": "missing or oversized body"})
            return
        try:
            body = self.rfile.read(length)
            parsed = json.loads(body.decode("utf-8"))
        except ValueError:
            # JSONDecodeError + UnicodeDecodeError both derive from
            # ValueError, so the bare catch covers "malformed JSON"
            # and "non-utf8 body" without redundant subclass listing.
            self._send_json(400, {"error": "invalid json"})
            return
        command = parse_payload(parsed)
        if command is None:
            self._send_json(400, {"error": "no group or speech"})
            return
        receiver.dispatch(command)
        self._send_json(200, {"ok": True})


class WebhookReceiver(QObject):
    """Lifecycle wrapper around :class:`ThreadingHTTPServer`.

    Construct cheaply; the socket only opens on :meth:`start`.
    Each parsed :class:`WebhookCommand` fires
    :attr:`command_received` on the Qt GUI thread (the worker
    thread emits, Qt's signal queue marshals).
    """

    command_received = Signal(str, str)
    """Emitted with ``(group, speech)`` for every successful
    POST /trigger. Either field may be empty when the caller
    only set one."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._port: int = DEFAULT_PORT
        self._token: str = ""
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ---- configuration -------------------------------------------

    def set_endpoint(self, port: int, token: str = "") -> None:   # nosec B107  # bearer token field; empty default means "no auth"
        """Cache the port + token. Effective on the next
        :meth:`start`; a running server stays on its current
        socket so a keystroke in the workspace settings doesn't
        thrash the OS port."""
        self._port = int(port) if port else DEFAULT_PORT
        self._token = str(token)

    def port(self) -> int:
        return self._port

    def token(self) -> str:
        return self._token

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- lifecycle -----------------------------------------------

    def start(self) -> bool:
        """Open the socket + spawn the serve thread. Returns
        ``True`` on success; ``False`` when the port is already
        in use (common cause: a previous Imervue session that
        crashed without closing) or refused by the OS."""
        if self.is_running():
            return True
        try:
            server = ThreadingHTTPServer(
                (DEFAULT_HOST, self._port), _WebhookHandler,
            )
        except (OSError, OverflowError) as exc:
            # OverflowError covers out-of-range ports (>65535);
            # OSError covers the more common "port in use" + DNS
            # failures. Both should fail gracefully rather than
            # take the pet down.
            logger.warning(
                "webhook bind failed on %s:%s: %s",
                DEFAULT_HOST, self._port, exc,
            )
            return False
        server.receiver = self   # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name=f"webhook-{self._port}",
            daemon=True,
        )
        self._thread.start()
        logger.info("webhook listening on %s:%s", DEFAULT_HOST, self._port)
        return True

    def stop(self) -> None:
        """Shut down the server + join the worker briefly. Safe to
        call on a never-started receiver."""
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except OSError as exc:
                logger.warning("webhook server shutdown: %s", exc)
        if thread is not None:
            thread.join(timeout=1.0)

    def shutdown(self) -> None:
        self.stop()

    # ---- dispatch -----------------------------------------------

    def dispatch(self, command: WebhookCommand) -> None:
        """Public hook for the HTTP handler — also reachable by
        tests that don't want to open a socket. Just re-emits the
        parsed command on the Qt signal."""
        self.command_received.emit(command.group, command.speech)
