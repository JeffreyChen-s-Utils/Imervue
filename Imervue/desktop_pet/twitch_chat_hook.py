"""Twitch chat → desktop-pet keyword hook.

Streamers map chat keywords to motion groups (``"hi"`` → ``Wave``,
``"thanks"`` → ``Bow``) so the pet reacts live during the broadcast.
Same group-name convention the OBS hook uses; the rig author opts
in by adding motions in those groups.

Implementation note: Twitch chat is plain IRC. We connect directly
via :mod:`socket` + :mod:`ssl` (Twitch's TLS port is 6697) and parse
the line-oriented PRIVMSG stream ourselves — ~80 lines, no third-
party deps, and avoids the OAuth client-app registration that the
``twitchio`` library requires. Users only need an *anonymous OAuth
token* from https://twitchapps.com/tmi (the same kind chat-bot
tutorials use).

The pure helpers (:func:`parse_chat_message`, :func:`match_keyword`)
are stateless string operations, easy to unit-test. The Qt wrapper
:class:`TwitchChatClient` owns a worker thread for the blocking
``recv`` loop and re-emits hits via thread-safe Qt signals.
"""
from __future__ import annotations

import contextlib
import logging
import socket
import ssl
import threading

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("Imervue.desktop_pet.twitch_chat_hook")

TWITCH_IRC_HOST: str = "irc.chat.twitch.tv"
TWITCH_IRC_TLS_PORT: int = 6697
"""Twitch IRC's TLS endpoint. The plain-text port (6667) exists but
we don't expose it — sending an OAuth token over a plain socket is
the wrong default to ship."""

_CONNECT_TIMEOUT_S: float = 10.0
_PRIVMSG_TOKEN: str = " PRIVMSG "   # noqa: S105  # IRC verb literal, not a credential


def parse_chat_message(line: str) -> dict[str, str] | None:
    """Parse an IRC PRIVMSG line into ``{user, channel, text}`` or
    return ``None`` if the line is anything else (PING, JOIN, NOTICE,
    or malformed garbage).

    Example input::

        :nightbot!nightbot@nightbot.tmi.twitch.tv PRIVMSG #channel :hello world

    The parser is permissive — anything that looks like the expected
    shape is accepted, anything else is dropped. We don't validate
    user / channel names because Twitch's rules drift and a strict
    parser would reject future variants.
    """
    if _PRIVMSG_TOKEN not in line:
        return None
    prefix, _, rest = line.partition(_PRIVMSG_TOKEN)
    if not prefix.startswith(":"):
        return None
    user_part = prefix[1:].split("!", 1)[0]
    if not user_part:
        return None
    channel_part, sep, text = rest.partition(" :")
    if not sep or not channel_part.startswith("#"):
        return None
    return {
        "user": user_part,
        "channel": channel_part[1:].split(" ", 1)[0],
        "text": text,
    }


def match_keyword(text: str, triggers: dict[str, str]) -> str | None:
    """Substring match ``text`` against the keys of ``triggers``,
    case-insensitive. Returns the mapped value (motion group / action
    name) or ``None`` when nothing matches.

    Iteration order matches dict insertion, so the first configured
    keyword in the dict wins on ties — gives the user a predictable
    way to prioritise overlapping triggers (place ``"raid"`` before
    ``"ai"`` if both fire on ``"raidaboo"``).
    """
    if not text:
        return None
    lowered = text.lower()
    for keyword, mapped in triggers.items():
        if keyword and keyword.lower() in lowered:
            return mapped
    return None


def coerce_triggers(raw: object) -> dict[str, str]:
    """Filter ``raw`` to a clean ``{keyword: mapped}`` dict — drops
    empty strings, non-string values, and non-dict inputs. Used by
    the settings loader so a typo'd entry doesn't break the rest
    of the trigger map."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            continue
        if not isinstance(value, str) or not value:
            continue
        out[key] = value
    return out


class TwitchChatClient(QObject):
    """QObject wrapping a raw-IRC connection to Twitch chat.

    The OS socket runs on a worker thread (``recv`` blocks); each
    parsed PRIVMSG is checked against the configured triggers and
    fired via :attr:`keyword_matched`, which queues onto the GUI
    thread when the receiver lives there.
    """

    keyword_matched = Signal(str)
    """Emitted with the *mapped* value (motion-group name or action
    id) each time a chat message contains one of the configured
    keywords."""

    connection_state_changed = Signal(bool)
    """``True`` after the IRC handshake succeeds, ``False`` after
    :meth:`stop` or a connection drop."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._channel: str = ""
        self._oauth: str = ""
        self._triggers: dict[str, str] = {}
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()

    # ---- public API ------------------------------------------------

    def set_endpoint(self, channel: str, oauth: str) -> None:
        """Cache the channel name + OAuth token. Effective on the
        next :meth:`start`; a running client stays on its current
        connection so a keystroke in the workspace doesn't thrash
        the socket."""
        self._channel = str(channel).lower().lstrip("#")
        self._oauth = str(oauth)

    def set_triggers(self, triggers: dict[str, str]) -> None:
        """Replace the trigger map. Safe to call while running —
        the worker thread reads the dict on each message."""
        self._triggers = coerce_triggers(triggers)

    def triggers(self) -> dict[str, str]:
        return dict(self._triggers)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Spawn the worker thread + open the socket. Returns
        ``True`` on a successful handshake; ``False`` when no
        channel / oauth is configured or the connection fails.
        Idempotent — a second start on a live client is a no-op."""
        if self.is_running():
            return True
        if not self._channel or not self._oauth:
            logger.info("twitch chat: channel + oauth required to start")
            return False
        try:
            sock = self._open_socket()
        except OSError as exc:
            logger.warning("twitch chat connect failed: %s", exc)
            return False
        self._sock = sock
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._run, name="twitch-chat", daemon=True,
        )
        self._thread.start()
        self.connection_state_changed.emit(True)
        return True

    def stop(self) -> None:
        """Signal the worker thread to exit and close the socket.
        Joins briefly so test-time teardowns are deterministic."""
        if self._thread is None:
            return
        self._stop_flag.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                sock.close()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)
        self.connection_state_changed.emit(False)

    def shutdown(self) -> None:
        self.stop()

    def process_line(self, line: str) -> None:
        """Public test hook — drive the parser without spawning the
        socket loop. Production code path goes through :meth:`_run`."""
        self._process_line(line)

    # ---- internal --------------------------------------------------

    def _open_socket(self) -> socket.socket:
        """Open a TLS-wrapped socket, perform the Twitch IRC
        handshake (PASS / NICK / JOIN), and return the socket. Raises
        :class:`OSError` on any failure so :meth:`start` can surface
        a single uniform error path."""
        ctx = ssl.create_default_context()
        # Explicit floor: Python 3.10+ defaults are already TLS 1.2,
        # but pinning here makes the policy obvious to reviewers
        # and survives a future ``create_default_context`` regression.
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        raw = socket.create_connection(
            (TWITCH_IRC_HOST, TWITCH_IRC_TLS_PORT), timeout=_CONNECT_TIMEOUT_S,
        )
        sock = ctx.wrap_socket(raw, server_hostname=TWITCH_IRC_HOST)
        sock.sendall(f"PASS {self._oauth}\r\n".encode())
        sock.sendall(f"NICK {self._channel}\r\n".encode())
        sock.sendall(f"JOIN #{self._channel}\r\n".encode())
        return sock

    def _run(self) -> None:
        """Worker-thread main loop. Reads chunks from the socket,
        splits on CRLF, and dispatches each line. Exits cleanly
        when :meth:`stop` is called or the socket closes."""
        sock = self._sock
        if sock is None:
            return
        buf = b""
        try:
            while not self._stop_flag.is_set():
                try:
                    chunk = sock.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\r\n" in buf:
                    line, _, buf = buf.partition(b"\r\n")
                    self._process_line(line.decode("utf-8", errors="replace"))
        except Exception as exc:   # noqa: BLE001 - any IRC error → drop the loop
            logger.warning("twitch chat loop: %s", exc)

    def _process_line(self, line: str) -> None:
        """Handle one IRC line. PING responds with PONG (keepalive),
        PRIVMSG fires keyword matching, everything else is dropped."""
        if line.startswith("PING"):
            sock = self._sock
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.sendall(b"PONG :tmi.twitch.tv\r\n")
            return
        msg = parse_chat_message(line)
        if msg is None:
            return
        mapped = match_keyword(msg["text"], self._triggers)
        if mapped is not None:
            self.keyword_matched.emit(mapped)
