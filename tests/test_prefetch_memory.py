"""Tests for the memory-pressure probes: psutil is optional and may fail."""
from __future__ import annotations

import sys

import pytest

from Imervue.gpu_image_view.prefetch_memory import PrefetchMemoryMixin as M


def test_probes_use_psutil_when_present():
    pytest.importorskip("psutil")
    assert M._process_rss_bytes() > 0  # noqa: SLF001
    assert M._ram_pressure_limit_bytes() >= 768 * 1024 * 1024  # noqa: SLF001


def test_missing_psutil_gives_the_fallbacks(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)   # import psutil -> ImportError
    assert M._process_rss_bytes() == 0  # noqa: SLF001
    assert M._ram_pressure_limit_bytes() == 2 * 1024 * 1024 * 1024  # noqa: SLF001


def test_failing_psutil_calls_give_the_fallbacks(monkeypatch):
    psutil = pytest.importorskip("psutil")

    def denied(*_a, **_k):
        raise psutil.AccessDenied()

    monkeypatch.setattr(psutil, "Process", denied)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: (_ for _ in ()).throw(OSError("x")))
    assert M._process_rss_bytes() == 0  # noqa: SLF001
    assert M._ram_pressure_limit_bytes() == 2 * 1024 * 1024 * 1024  # noqa: SLF001


def test_unexpected_psutil_error_propagates(monkeypatch):
    psutil = pytest.importorskip("psutil")

    def bug(*_a, **_k):
        raise RuntimeError("bug")

    monkeypatch.setattr(psutil, "Process", bug)
    with pytest.raises(RuntimeError):
        M._process_rss_bytes()  # noqa: SLF001
