"""Which ``Origin`` headers a localhost server accepts."""
from __future__ import annotations

import pytest

from Imervue.system.local_origin import is_allowed_origin


@pytest.mark.parametrize("origin", [
    None, "", "null", "file://", "file:///C:/trackers/index.html",
    "http://localhost:3000", "https://localhost", "http://127.0.0.1:8080", "http://[::1]:5000",
    "chrome-extension://abcdef",
])
def test_allowed_origins(origin):
    assert is_allowed_origin(origin)


@pytest.mark.parametrize("origin", [
    "https://evil.example", "http://attacker.test:8001", "HTTPS://Example.COM",
    "http://localhost.evil.example", "http://127.0.0.1.nip.io",
])
def test_web_origins_are_refused(origin):
    assert not is_allowed_origin(origin)
