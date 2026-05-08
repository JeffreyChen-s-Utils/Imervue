"""Tests for the autosave recovery prompt at workspace launch."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    monkeypatch.setattr(
        "Imervue.paint.auto_save.default_autosave_dir",
        lambda: tmp_path / "autosave-stash",
    )
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


class _StubToast:
    def __init__(self, sink):
        self._sink = sink

    def info(self, text, duration_ms=2500):
        self._sink.append(("info", text))

    def success(self, text, duration_ms=2500):
        self._sink.append(("success", text))

    def warning(self, text, duration_ms=3000):
        self._sink.append(("warning", text))

    def error(self, text, duration_ms=4000):
        self._sink.append(("error", text))


def test_no_recovery_prompt_on_clean_boot(qapp):
    ws = PaintWorkspace()
    try:
        sink = []
        ws.toast = _StubToast(sink)
        ws._maybe_offer_autosave_recovery()  # noqa: SLF001
        assert sink == []
    finally:
        ws.deleteLater()


def test_recovery_prompt_fires_when_snapshots_present(qapp, monkeypatch):
    monkeypatch.setattr(
        PaintWorkspace, "pending_autosaves",
        lambda self, *, target_dir=None: [object(), object()],
    )
    ws = PaintWorkspace()
    try:
        sink = []
        ws.toast = _StubToast(sink)
        ws._maybe_offer_autosave_recovery()  # noqa: SLF001
        assert sink
        level, text = sink[0]
        assert level == "warning"
        assert "2" in text or "snapshot" in text.lower()
    finally:
        ws.deleteLater()


def test_recovery_prompt_falls_back_to_status_bar(qapp, monkeypatch):
    monkeypatch.setattr(
        PaintWorkspace, "pending_autosaves",
        lambda self, *, target_dir=None: [object()],
    )
    ws = PaintWorkspace()
    try:
        ws.toast = None
        ws._maybe_offer_autosave_recovery()  # noqa: SLF001
        assert ws._status.currentMessage()  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_recovery_prompt_swallows_io_error(qapp, monkeypatch):
    def _fail(self, *, target_dir=None):
        raise OSError("permission denied")
    monkeypatch.setattr(PaintWorkspace, "pending_autosaves", _fail)
    ws = PaintWorkspace()
    try:
        ws._maybe_offer_autosave_recovery()  # noqa: SLF001
    finally:
        ws.deleteLater()
