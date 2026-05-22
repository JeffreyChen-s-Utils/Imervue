"""Tests for the local-LLM dialogue client.

Two layers (same pattern as the OBS / Twitch hooks):

* **Pure helpers** (``validate_base_url``, ``build_prompt``,
  ``extract_line``, ``_request_json`` via monkey-patched
  ``urllib.request.urlopen``) cover the URL policy and response
  parsing without spawning threads.
* **Client lifecycle** uses a stubbed ``_request_json`` so no real
  HTTP request fires. Each call still goes through the worker
  thread to verify the threading wiring; ``thread.join`` makes
  the result deterministic.
"""
from __future__ import annotations

import json
import time

import pytest

from Imervue.desktop_pet import llm_dialogue
from Imervue.desktop_pet.llm_dialogue import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_PERSONA,
    LlmDialogueClient,
    build_prompt,
    extract_line,
    validate_base_url,
)


# ---------------------------------------------------------------
# validate_base_url
# ---------------------------------------------------------------


def test_validate_base_url_accepts_loopback_http():
    """The whole point of HTTP-on-loopback: Ollama listens on plain
    HTTP at 127.0.0.1 by default — must be allowed without making
    the user run a TLS proxy."""
    validate_base_url("http://localhost:11434")
    validate_base_url("http://127.0.0.1:11434")
    validate_base_url("http://[::1]:11434")


def test_validate_base_url_rejects_plain_http_remote():
    """Sending an LLM prompt unencrypted across a network is the
    kind of "oh no" we want a fail-loud about, not a silent
    misconfiguration."""
    with pytest.raises(ValueError):
        validate_base_url("http://example.com:11434")
    with pytest.raises(ValueError):
        validate_base_url("http://192.168.1.5:11434")


def test_validate_base_url_accepts_https_anywhere():
    """HTTPS is allowed everywhere — users running a remote Ollama
    can put it behind TLS."""
    validate_base_url("https://ollama.example.com")
    validate_base_url("https://localhost:8443")


def test_validate_base_url_rejects_unknown_scheme():
    """File / ftp / no-scheme: all rejected. Catches typos like
    ``localhost:11434`` (missing scheme parses as scheme=)."""
    for url in ("ftp://localhost", "file:///etc/ollama", "no-scheme"):
        with pytest.raises(ValueError):
            validate_base_url(url)


# ---------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------


def test_build_prompt_includes_persona_and_situation():
    out = build_prompt("you are a robot", "greeting")
    assert "you are a robot" in out
    assert "greeting" in out
    assert "Message:" in out


def test_build_prompt_falls_back_when_persona_blank():
    """Empty persona → default persona embedded — better than a
    bare 'reply' prompt that yields chatty multi-paragraph output."""
    out = build_prompt("", "")
    assert DEFAULT_PERSONA in out
    assert "Situation: greeting" in out


# ---------------------------------------------------------------
# extract_line
# ---------------------------------------------------------------


def test_extract_line_happy_path():
    """Standard Ollama envelope → strip-and-return."""
    assert extract_line({"response": "Hello!", "done": True}) == "Hello!"


def test_extract_line_strips_quotes_and_whitespace():
    """Small models often wrap output in quotes or leading newline.
    Strip them so the speech bubble doesn't pop with ``\"hi\"``."""
    assert extract_line({"response": '"Hi there!"  '}) == "Hi there!"
    assert extract_line({"response": "  '\nHey'  "}) == "Hey"


def test_extract_line_empty_returns_none():
    """Empty / whitespace-only → None so the caller falls back
    rather than showing a blank bubble."""
    assert extract_line({"response": ""}) is None
    assert extract_line({"response": "   "}) is None


def test_extract_line_missing_field_returns_none():
    """Malformed response (Ollama returned an error envelope) →
    None instead of KeyError on the GUI thread."""
    assert extract_line({"error": "model not found"}) is None
    assert extract_line({}) is None


def test_extract_line_non_dict_returns_none():
    """Defensive against ``_request_json`` returning a list or
    string by accident."""
    assert extract_line([]) is None    # type: ignore[arg-type]
    assert extract_line("string") is None   # type: ignore[arg-type]


# ---------------------------------------------------------------
# _request_json — uses urllib.request.urlopen, stub it
# ---------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


def test_request_json_returns_parsed_dict(monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["timeout"] = timeout
        return _FakeResponse(b'{"response": "ok"}')

    monkeypatch.setattr(llm_dialogue.urllib.request, "urlopen", fake_urlopen)
    out = llm_dialogue._request_json(   # noqa: SLF001
        "http://localhost:11434/api/generate",
        {"prompt": "x"}, timeout=5.0,
    )
    assert out == {"response": "ok"}
    assert captured["url"].endswith("/api/generate")
    assert json.loads(captured["body"])["prompt"] == "x"
    assert captured["timeout"] == 5.0


def test_request_json_validates_url_before_dialling(monkeypatch):
    """A bad URL must raise immediately — no network call."""
    called = {"n": 0}

    def should_not_call(*_args, **_kw):
        called["n"] += 1
        return _FakeResponse(b"{}")

    monkeypatch.setattr(llm_dialogue.urllib.request, "urlopen", should_not_call)
    with pytest.raises(ValueError):
        llm_dialogue._request_json(   # noqa: SLF001
            "http://example.com/api", {}, timeout=1.0,
        )
    assert called["n"] == 0


# ---------------------------------------------------------------
# LlmDialogueClient — threaded
# ---------------------------------------------------------------


def test_client_defaults_match_module_constants(qapp):
    client = LlmDialogueClient()
    assert client.base_url() == DEFAULT_BASE_URL
    assert client.model() == DEFAULT_MODEL
    assert client.persona() == DEFAULT_PERSONA


def test_client_set_endpoint_validates(qapp):
    """Bad URL on set_endpoint → ValueError so the workspace can
    bounce the user back to the input box with an error."""
    client = LlmDialogueClient()
    with pytest.raises(ValueError):
        client.set_endpoint(base_url="http://remote-server")


def _wait_for(qapp, predicate, timeout_s: float = 2.0) -> bool:
    """Pump the Qt event loop until ``predicate`` is true or the
    timeout elapses. Queued signals from the worker thread land on
    the GUI thread only when the event loop is processed — without
    this the worker emits but the test's connected lambda never
    runs."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return predicate()


def test_client_request_emits_line_on_success(qapp, monkeypatch):
    """Happy path — stub the request, drive a worker through to
    completion, signal fires with the extracted line."""
    monkeypatch.setattr(
        llm_dialogue, "_request_json",
        lambda *_a, **_kw: {"response": "Hello from llm"},
    )
    client = LlmDialogueClient()
    received: list[str] = []
    client.line_received.connect(received.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(received))
    assert received == ["Hello from llm"]


def test_client_request_emits_failed_on_value_error(qapp, monkeypatch):
    """A misconfigured URL inside the worker routes through
    ``request_failed``, not an uncaught exception."""
    def boom(*_a, **_kw):
        raise ValueError("bad config")

    monkeypatch.setattr(llm_dialogue, "_request_json", boom)
    client = LlmDialogueClient()
    errors: list[str] = []
    client.request_failed.connect(errors.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(errors))
    assert "config" in errors[0]


def test_client_request_emits_failed_on_timeout(qapp, monkeypatch):
    def boom(*_a, **_kw):
        raise TimeoutError("model warming up")

    monkeypatch.setattr(llm_dialogue, "_request_json", boom)
    client = LlmDialogueClient()
    errors: list[str] = []
    client.request_failed.connect(errors.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(errors))
    assert "network" in errors[0]


def test_client_request_emits_failed_on_empty_response(qapp, monkeypatch):
    """Ollama returned 200 with empty content — must NOT pop an
    empty speech bubble. Routes to request_failed instead."""
    monkeypatch.setattr(
        llm_dialogue, "_request_json", lambda *_a, **_kw: {"response": ""},
    )
    client = LlmDialogueClient()
    errors: list[str] = []
    client.request_failed.connect(errors.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(errors))
    assert errors == ["empty response"]


def test_client_request_emits_failed_on_unknown_exception(qapp, monkeypatch):
    """Last-ditch catch — even an unexpected runtime error must
    route to ``request_failed`` so the GUI thread never sees the
    blow-up."""
    def boom(*_a, **_kw):
        raise RuntimeError("surprise")

    monkeypatch.setattr(llm_dialogue, "_request_json", boom)
    client = LlmDialogueClient()
    errors: list[str] = []
    client.request_failed.connect(errors.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(errors))
    assert "unknown" in errors[0]


def test_client_set_endpoint_takes_effect_on_next_request(qapp, monkeypatch):
    """Each request reads from the current config so workspace
    edits take effect immediately — no client restart required."""
    captured: list[str] = []

    def capture(url, payload, timeout):
        captured.append(url)
        return {"response": "ok"}

    monkeypatch.setattr(llm_dialogue, "_request_json", capture)
    client = LlmDialogueClient()
    client.set_endpoint(
        base_url="http://localhost:11434",
        model="custom-model",
        persona="custom",
    )
    received: list[str] = []
    client.line_received.connect(received.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(received))
    assert captured[0] == "http://localhost:11434/api/generate"
