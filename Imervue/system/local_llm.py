"""JSON over HTTP to a local LLM server (Ollama by default): the URL policy and the POST.

Qt-free and import-light, so the image caption feature and the desktop pet's
dialogue share it without one loading the other. The policy is "loopback
``http://`` or any ``https://``": a local server needs no TLS, and anything
remote must use it.
"""
from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlparse

LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_base_url(url: str) -> None:
    """Raise :class:`ValueError` unless ``url`` is loopback ``http://`` or any ``https://``."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme: {parsed.scheme!r}")
    if parsed.scheme == "http" and (parsed.hostname or "") not in LOOPBACK_HOSTS:
        raise ValueError(
            "plain HTTP is only allowed for loopback hosts "
            "(localhost / 127.0.0.1 / ::1); use HTTPS for remote",
        )


def post_json(url: str, payload: dict, timeout: float) -> dict:
    """POST ``payload`` as JSON to ``url`` and return the decoded JSON response.

    The URL is checked with :func:`validate_base_url` first, so a bad one
    raises ``ValueError`` before any connection; network failures raise
    ``urllib.error.URLError`` / ``OSError``.
    """
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
