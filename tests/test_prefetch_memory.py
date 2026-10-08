"""Tests for the memory-pressure probes: psutil is optional and may fail."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np

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


def test_ram_cache_decisions_do_not_depend_on_vram_capacity():
    calls = []
    view = SimpleNamespace(
        deep_zoom=SimpleNamespace(levels=[np.zeros(30, dtype=np.uint8)]),
        _prefetch=SimpleNamespace(budget=SimpleNamespace(limit_bytes=100)),
        _filmstrip_thumb_cache={"cached": object()}, _filmstrip_pending={"pending"},
        _vram_limit=1, tile_manager=None,
        _process_rss_bytes=lambda: 0, _cancel_all_prefetch=lambda: calls.append("cancel"),
    )
    M.enforce_memory_pressure(view)
    assert not calls
    assert not view._filmstrip_thumb_cache
    view.deep_zoom.levels = [np.zeros(36, dtype=np.uint8)]
    view._vram_limit = 1000000
    M.enforce_memory_pressure(view)
    assert calls == ["cancel"]
