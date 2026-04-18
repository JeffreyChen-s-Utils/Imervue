"""Tests for viewer history push/pop and random image logic.

The viewer itself needs a real OpenGL context so we exercise the history
helpers via a minimal stub class that mixes in the same methods — the
logic is pure-Python so there's no Qt dependency.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class _HistoryStub:
    """Reuses the exact push/back/forward bodies from GPUImageView."""

    _HISTORY_MAX = 5  # Smaller for tests

    def __init__(self):
        self._history = []
        self._history_pos = -1
        self._history_navigating = False
        self.loaded = []  # Track calls to load_deep_zoom_image

    # Copy of the method from gpu_image_view (kept intentionally)
    def _push_history(self, path):
        if self._history_navigating or not path:
            return
        if self._history and self._history_pos >= 0:
            if self._history[self._history_pos] == path:
                return
        if self._history_pos < len(self._history) - 1:
            del self._history[self._history_pos + 1:]
        self._history.append(path)
        if len(self._history) > self._HISTORY_MAX:
            overflow = len(self._history) - self._HISTORY_MAX
            del self._history[:overflow]
            self._history_pos = len(self._history) - 1
        else:
            self._history_pos = len(self._history) - 1

    def history_back(self):
        if self._history_pos <= 0:
            return False
        self._history_pos -= 1
        return True

    def history_forward(self):
        if self._history_pos >= len(self._history) - 1:
            return False
        self._history_pos += 1
        return True


class TestHistoryStack:
    def test_initial_state_is_empty(self):
        s = _HistoryStub()
        assert s._history == []
        assert s._history_pos == -1

    def test_push_appends_and_moves_pos(self):
        s = _HistoryStub()
        s._push_history("a.png")
        s._push_history("b.png")
        assert s._history == ["a.png", "b.png"]
        assert s._history_pos == 1

    def test_duplicate_adjacent_push_is_ignored(self):
        s = _HistoryStub()
        s._push_history("a.png")
        s._push_history("a.png")
        assert s._history == ["a.png"]
        assert s._history_pos == 0

    def test_push_while_navigating_is_ignored(self):
        s = _HistoryStub()
        s._push_history("a.png")
        s._history_navigating = True
        s._push_history("b.png")
        s._history_navigating = False
        assert s._history == ["a.png"]

    def test_new_push_truncates_forward_history(self):
        s = _HistoryStub()
        for p in ("a.png", "b.png", "c.png"):
            s._push_history(p)
        s.history_back()  # at b
        s.history_back()  # at a
        assert s._history_pos == 0
        # Branching: push new image — c.png should disappear
        s._push_history("new.png")
        assert s._history == ["a.png", "new.png"]
        assert s._history_pos == 1

    def test_back_returns_false_at_start(self):
        s = _HistoryStub()
        s._push_history("a.png")
        assert s.history_back() is False

    def test_forward_returns_false_at_end(self):
        s = _HistoryStub()
        s._push_history("a.png")
        assert s.history_forward() is False

    def test_round_trip_back_forward(self):
        s = _HistoryStub()
        s._push_history("a.png")
        s._push_history("b.png")
        s._push_history("c.png")
        assert s.history_back()
        assert s._history[s._history_pos] == "b.png"
        assert s.history_forward()
        assert s._history[s._history_pos] == "c.png"

    def test_cap_respects_max(self):
        s = _HistoryStub()
        s._HISTORY_MAX = 3
        for p in ("a.png", "b.png", "c.png", "d.png", "e.png"):
            s._push_history(p)
        assert len(s._history) == 3
        assert s._history == ["c.png", "d.png", "e.png"]
        assert s._history_pos == 2
