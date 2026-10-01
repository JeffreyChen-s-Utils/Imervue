"""The local-LLM HTTP helpers shared by image captions and the desktop pet's dialogue."""
from __future__ import annotations

import json

import pytest

from Imervue.system import local_llm
from Imervue.system.local_llm import validate_base_url


# ---------------------------------------------------------------
# validate_base_url
# ---------------------------------------------------------------


def test_validate_base_url_accepts_loopback_http():
    """The whole point of HTTP-on-loopback: Ollama listens on plain
    HTTP at 127.0.0.1 by default — must be allowed without making
    the user run a TLS proxy."""
    validate_base_url("http://localhost:11434")   # NOSONAR  # loopback HTTP literal under test
    validate_base_url("http://127.0.0.1:11434")   # NOSONAR  # loopback HTTP literal under test
    validate_base_url("http://[::1]:11434")       # NOSONAR  # loopback HTTP literal under test


def test_validate_base_url_rejects_plain_http_remote():
    """Sending an LLM prompt unencrypted across a network is the
    kind of "oh no" we want a fail-loud about, not a silent
    misconfiguration."""
    with pytest.raises(ValueError):
        validate_base_url("http://example.com:11434")   # NOSONAR  # negative-case fixture; the validator must reject it
    with pytest.raises(ValueError):
        validate_base_url("http://192.168.1.5:11434")   # NOSONAR  # negative-case fixture; the validator must reject it


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
# post_json — uses urllib.request.urlopen, stub it
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


def test_post_json_returns_parsed_dict(monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["timeout"] = timeout
        return _FakeResponse(b'{"response": "ok"}')

    monkeypatch.setattr(local_llm.urllib.request, "urlopen", fake_urlopen)
    out = local_llm.post_json(
        "http://localhost:11434/api/generate",   # NOSONAR  # loopback HTTP literal under test
        {"prompt": "x"}, timeout=5.0,
    )
    assert out == {"response": "ok"}
    assert captured["url"].endswith("/api/generate")
    assert json.loads(captured["body"])["prompt"] == "x"
    assert captured["timeout"] == 5.0   # NOSONAR  # exact representable value asserted intentionally


def test_post_json_validates_url_before_dialling(monkeypatch):
    """A bad URL must raise immediately — no network call."""
    called = {"n": 0}

    def should_not_call(*_args, **_kw):
        called["n"] += 1
        return _FakeResponse(b"{}")

    monkeypatch.setattr(local_llm.urllib.request, "urlopen", should_not_call)
    with pytest.raises(ValueError):
        local_llm.post_json(
            "http://example.com/api",   # NOSONAR  # negative-case fixture; the guard must reject it
            {}, timeout=1.0,
        )
    assert called["n"] == 0
