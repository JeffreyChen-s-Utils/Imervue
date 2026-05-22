"""Local-LLM dialogue client for the desktop pet.

The scripted speech engine (:mod:`Imervue.desktop_pet.pet_script`)
gives the pet a fixed pool of lines per bucket. That's robust and
fast, but a long-running pet eventually feels like a stuck record.
This module connects to a *local* LLM (default: an Ollama server
running on ``localhost:11434``) so the pet can generate fresh lines
per click — same speech-bubble UX, dynamic content.

Why local-only by default: pets chat constantly, and routing every
greeting through a paid API would burn through credits and leak
"my desktop pet says hi" requests to a third party. Ollama runs the
model on the user's machine, never touching the network. Remote
LLMs are still supported via HTTPS base URLs for users who want
that — the URL guard accepts ``https://`` anywhere, ``http://``
only on localhost.

The class is structured to mirror the other optional-dep clients
in this package (``ObsEventClient``, ``TwitchChatClient``): pure
helpers are stateless and Qt-free, the QObject wrapper runs the
blocking HTTP call on a worker thread, and signal emissions queue
back onto the GUI thread.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    pass

logger = logging.getLogger("Imervue.desktop_pet.llm_dialogue")

DEFAULT_BASE_URL: str = "http://localhost:11434"
"""Ollama's default listen address. The HTTP scheme is fine because
the URL guard restricts ``http://`` to loopback only."""

DEFAULT_MODEL: str = "llama3.2:1b"
"""Smallest commonly-pulled Ollama model — completes a short
greeting in well under a second on CPU. Heavier models work too;
the user picks via settings."""

DEFAULT_PERSONA: str = (
    "You are a cheerful desktop pet living on the user's screen. "
    "Reply with ONE short, warm message (under 15 words). "
    "No quotation marks, no preamble, just the message itself."
)
"""System-prompt persona. Kept terse on purpose — long prompts
slow first-token latency on local CPU inference, and the speech
bubble can't show much text anyway."""

DEFAULT_TIMEOUT_S: float = 8.0
"""Hard cap on how long the user waits for a reply. Local models
on CPU can take a few seconds; 8 s leaves margin without making a
broken Ollama install feel like a hang."""

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_base_url(url: str) -> None:
    """Raise :class:`ValueError` when ``url`` doesn't meet the
    "loopback http or any https" policy. Pure helper so the
    settings-validation path can call it without spawning a
    request."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme: {parsed.scheme!r}")
    if parsed.scheme == "http" and (parsed.hostname or "") not in _LOOPBACK_HOSTS:
        raise ValueError(
            "plain HTTP is only allowed for loopback hosts "
            "(localhost / 127.0.0.1 / ::1); use HTTPS for remote",
        )


def build_prompt(persona: str, situation: str) -> str:
    """Compose the prompt the LLM sees.

    ``situation`` is one of ``"greeting"``, ``"hit:<area>"``,
    ``"motion:<name>"``, ``"time_of_day:<band>"``, free-form. The
    persona stays on top; the situation tag goes in a labelled
    section so a small model has a clear pattern to follow."""
    persona = (persona or DEFAULT_PERSONA).strip()
    situation = (situation or "greeting").strip()
    return (
        f"{persona}\n\n"
        f"Situation: {situation}\n"
        f"Message:"
    )


def extract_line(response_payload: dict) -> str | None:
    """Pull the message string out of Ollama's response envelope.

    Ollama's ``/api/generate`` (non-streaming) returns
    ``{"response": "...", "done": True, ...}``. We strip
    quotes / outer whitespace and reject empty strings so the
    speech bubble never pops with an empty line."""
    raw = response_payload.get("response") if isinstance(response_payload, dict) else None
    if not isinstance(raw, str):
        return None
    text = raw.strip().strip('"').strip("'").strip()
    if not text:
        return None
    return text


def _request_json(url: str, payload: dict, timeout: float) -> dict:
    """POST ``payload`` as JSON to ``url`` and return the decoded
    JSON response. ``validate_base_url`` must already have approved
    the scheme/host pair — this is the wire-format step."""
    validate_base_url(url)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # scheme + host validated above
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


class LlmDialogueClient(QObject):
    """Async LLM client. Fire-and-forget per request; results come
    back via :attr:`line_received` / :attr:`request_failed`.

    Each :meth:`request_line` call spawns a daemon thread so the
    GUI never blocks waiting for the model. The previous request's
    thread is *not* cancelled — Python doesn't expose a clean way to
    interrupt a blocking ``urlopen``. If two requests overlap, both
    will eventually emit; the receiver should ignore stale results
    based on its own state (e.g. "is the bubble still up?").
    """

    line_received = Signal(str)
    """Emitted with the LLM's reply string on success. Stripped of
    surrounding quotes and whitespace."""

    request_failed = Signal(str)
    """Emitted with a short error message on any failure (bad URL,
    timeout, connection refused, malformed response). The receiver
    typically falls back to the scripted line set."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._base_url: str = DEFAULT_BASE_URL
        self._model: str = DEFAULT_MODEL
        self._persona: str = DEFAULT_PERSONA
        self._timeout_s: float = DEFAULT_TIMEOUT_S

    # ---- configuration -------------------------------------------

    def set_endpoint(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        persona: str = DEFAULT_PERSONA,
    ) -> None:
        """Cache the endpoint params. URL is validated immediately;
        :class:`ValueError` propagates so the caller can reject the
        user's typed URL with a clear message."""
        validate_base_url(base_url)
        self._base_url = base_url
        self._model = str(model) or DEFAULT_MODEL
        self._persona = str(persona) or DEFAULT_PERSONA

    def base_url(self) -> str:
        return self._base_url

    def model(self) -> str:
        return self._model

    def persona(self) -> str:
        return self._persona

    # ---- fire a request ------------------------------------------

    def request_line(self, situation: str = "greeting") -> None:
        """Spawn a worker thread, hit the LLM, emit the result.
        Returns immediately — the actual response lands later via
        :attr:`line_received` / :attr:`request_failed`."""
        prompt = build_prompt(self._persona, situation)
        thread = threading.Thread(
            target=self._run_request,
            args=(prompt,),
            name=f"llm-dialogue-{situation[:16]}",
            daemon=True,
        )
        thread.start()

    def _run_request(self, prompt: str) -> None:
        """Worker-thread body. Catches every exception and routes
        it through :attr:`request_failed` so a misbehaving LLM
        can't take the GUI thread down with it."""
        url = self._base_url.rstrip("/") + "/api/generate"
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        try:
            data = _request_json(url, payload, timeout=self._timeout_s)
        except urllib.error.URLError as exc:
            logger.info("llm request URLError: %s", exc)
            self.request_failed.emit(f"connection: {exc}")
            return
        except (TimeoutError, OSError) as exc:
            logger.info("llm request OSError: %s", exc)
            self.request_failed.emit(f"network: {exc}")
            return
        except ValueError as exc:
            logger.warning("llm bad URL / payload: %s", exc)
            self.request_failed.emit(f"config: {exc}")
            return
        except Exception as exc:   # noqa: BLE001 - last-ditch safety on the worker thread
            logger.warning("llm request unexpected: %s", exc)
            self.request_failed.emit(f"unknown: {exc}")
            return
        line = extract_line(data)
        if line is None:
            self.request_failed.emit("empty response")
            return
        self.line_received.emit(line)
