"""Tests for TimelineModel transient-failure thumbnail retry.

A timeline thumbnail that fails to decode (file mid-move/delete or briefly
locked) must retry instead of caching a permanent dark placeholder. A fake
pool captures re-queues so no real worker runs.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def timeline_model(qapp):
    from Imervue.gui.timeline_view import TimelineModel
    return TimelineModel


def _pixmap():
    from PySide6.QtGui import QPixmap
    return QPixmap(96, 96)


def _build(model_cls, path, monkeypatch):
    m = model_cls([path])
    started: list = []
    monkeypatch.setattr(m._pool, "start", started.append)  # noqa: SLF001
    return m, started


class TestTimelineThumbRetry:
    def test_success_caches_and_clears_state(self, timeline_model, tmp_path, monkeypatch):
        p = str(tmp_path / "a.png")
        m, _started = _build(timeline_model, p, monkeypatch)
        m._on_thumb(p, _pixmap(), True)  # noqa: SLF001
        _, entry = m._entry_index(p)  # noqa: SLF001
        assert entry.fetched is True
        assert entry.icon is not None
        assert p not in m._in_flight  # noqa: SLF001
        assert p not in m._retry  # noqa: SLF001

    def test_transient_failure_requeues_without_caching(self, timeline_model, tmp_path, monkeypatch):
        p = str(tmp_path / "a.png")
        m, started = _build(timeline_model, p, monkeypatch)
        m._on_thumb(p, _pixmap(), False)  # noqa: SLF001
        _, entry = m._entry_index(p)  # noqa: SLF001
        assert entry.fetched is False
        assert m._retry[p] == 1  # noqa: SLF001
        assert p in m._in_flight  # noqa: SLF001
        assert len(started) == 1

    def test_failure_caps_then_falls_back_to_placeholder(self, timeline_model, tmp_path, monkeypatch):
        from Imervue.gui.timeline_view import _MAX_THUMB_RETRIES
        p = str(tmp_path / "a.png")
        m, _started = _build(timeline_model, p, monkeypatch)
        for _ in range(_MAX_THUMB_RETRIES):
            m._on_thumb(p, _pixmap(), False)  # noqa: SLF001
        assert m._entry_index(p)[1].fetched is False  # noqa: SLF001
        m._on_thumb(p, _pixmap(), False)  # noqa: SLF001
        _, entry = m._entry_index(p)  # noqa: SLF001
        assert entry.fetched is True
        assert p not in m._retry  # noqa: SLF001

    def test_late_callback_for_removed_path_is_ignored(self, timeline_model, tmp_path, monkeypatch):
        p = str(tmp_path / "a.png")
        m, _started = _build(timeline_model, p, monkeypatch)
        m._on_thumb(str(tmp_path / "gone.png"), _pixmap(), True)  # noqa: SLF001
        assert m._entry_index(p)[1].fetched is False  # noqa: SLF001
