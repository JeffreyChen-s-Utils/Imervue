"""Tests for the local-LLM dialogue client.

Two layers (same pattern as the OBS / Twitch hooks):

* **Pure helpers** (``build_prompt``, ``extract_line``) cover the
  prompt and response parsing without spawning threads; the URL
  policy and the POST are tested in ``test_local_llm.py``.
* **Client lifecycle** uses a stubbed ``post_json`` so no real
  HTTP request fires. Each call still goes through the worker
  thread to verify the threading wiring; ``thread.join`` makes
  the result deterministic.
"""
from __future__ import annotations

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
)


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
    assert extract_line([]) is None    # type: ignore[arg-type]  # NOSONAR  # negative-case fixture: helper must tolerate wrong type
    assert extract_line("string") is None   # type: ignore[arg-type]  # NOSONAR  # negative-case fixture: helper must tolerate wrong type


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
        client.set_endpoint(base_url="http://remote-server")   # NOSONAR  # negative-case fixture; the setter must reject it


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


def test_shutdown_suppresses_late_emits(qapp):
    """After shutdown the client must not emit -- a request still blocked in
    urlopen would otherwise fire on a QObject the window has deleted."""
    client = LlmDialogueClient()
    lines: list = []
    errors: list = []
    client.line_received.connect(lines.append)
    client.request_failed.connect(errors.append)
    # Alive: the safe wrappers deliver synchronously (same-thread connection).
    client._safe_line("hi")
    client._safe_fail("err")
    assert lines == ["hi"]
    assert errors == ["err"]
    # Dead: dropped.
    client.shutdown()
    client._safe_line("late")
    client._safe_fail("late-err")
    assert lines == ["hi"]
    assert errors == ["err"]


def test_controller_shutdown_marks_its_client_dead():
    from types import SimpleNamespace

    from Imervue.desktop_pet.pet_drivers import LlmDialogueController

    marked: list = []
    ctrl = SimpleNamespace(
        _client=SimpleNamespace(shutdown=lambda: marked.append(True)))
    LlmDialogueController.shutdown(ctrl)
    assert marked == [True]
    # A controller that never built a client is a safe no-op.
    LlmDialogueController.shutdown(SimpleNamespace(_client=None))


def test_client_request_emits_line_on_success(qapp, monkeypatch):
    """Happy path — stub the request, drive a worker through to
    completion, signal fires with the extracted line."""
    monkeypatch.setattr(
        llm_dialogue, "post_json",
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

    monkeypatch.setattr(llm_dialogue, "post_json", boom)
    client = LlmDialogueClient()
    errors: list[str] = []
    client.request_failed.connect(errors.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(errors))
    assert "config" in errors[0]


def test_client_request_emits_failed_on_timeout(qapp, monkeypatch):
    def boom(*_a, **_kw):
        raise TimeoutError("model warming up")

    monkeypatch.setattr(llm_dialogue, "post_json", boom)
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
        llm_dialogue, "post_json", lambda *_a, **_kw: {"response": ""},
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

    monkeypatch.setattr(llm_dialogue, "post_json", boom)
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

    monkeypatch.setattr(llm_dialogue, "post_json", capture)
    client = LlmDialogueClient()
    client.set_endpoint(
        base_url="http://localhost:11434",   # NOSONAR  # loopback HTTP literal under test
        model="custom-model",
        persona="custom",
    )
    received: list[str] = []
    client.line_received.connect(received.append)
    client.request_line("greeting")
    assert _wait_for(qapp, lambda: bool(received))
    assert captured[0] == "http://localhost:11434/api/generate"   # NOSONAR  # loopback HTTP literal under test
