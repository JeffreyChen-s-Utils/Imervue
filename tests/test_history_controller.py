"""Tests for HistoryController — browsing history (Alt+←/→) navigation.

Uses a minimal fake view so no Qt / GL context is needed; the controller's
logic is pure-Python apart from the view callbacks it invokes on navigate.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.history_controller import HistoryController


class _FakeModel:
    def __init__(self, images):
        self.images = list(images)


def _make_view(images, *, files_exist=True):
    view = SimpleNamespace(
        model=_FakeModel(images),
        current_index=0,
        tile_grid_mode=False,
        loaded=[],
    )
    view._clear_deep_zoom = lambda: None
    view.load_deep_zoom_image = lambda p: view.loaded.append(p)
    return view


def test_initial_state_no_navigation():
    ctrl = HistoryController(_make_view([]))
    assert ctrl.back() is False
    assert ctrl.forward() is False


def test_push_then_back_and_forward(monkeypatch):
    view = _make_view(["a", "b", "c"])
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("a")
    ctrl.push("b")
    ctrl.push("c")
    assert ctrl.back() is True
    assert view.loaded[-1] == "b"
    assert ctrl.forward() is True
    assert view.loaded[-1] == "c"


def test_back_at_start_returns_false():
    view = _make_view(["a"])
    ctrl = HistoryController(view)
    ctrl.push("a")
    assert ctrl.back() is False


def test_forward_at_end_returns_false():
    view = _make_view(["a"])
    ctrl = HistoryController(view)
    ctrl.push("a")
    assert ctrl.forward() is False


def test_adjacent_duplicate_not_pushed():
    ctrl = HistoryController(_make_view(["a"]))
    ctrl.push("a")
    ctrl.push("a")
    # Only one entry → back is impossible.
    assert ctrl.back() is False


def test_empty_path_is_ignored():
    ctrl = HistoryController(_make_view(["a"]))
    ctrl.push("")
    assert ctrl.back() is False


def test_push_suppressed_while_navigating(monkeypatch):
    view = _make_view(["a", "b"])
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("a")
    ctrl.push("b")
    # Navigating back loads "a" but must not re-push it.
    ctrl.back()
    assert view.loaded[-1] == "a"
    # Forward must still work (b is still in the stack).
    assert ctrl.forward() is True


def test_new_push_truncates_forward_history(monkeypatch):
    view = _make_view(["a", "b", "c", "new"])
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    for path in ("a", "b", "c"):
        ctrl.push(path)
    ctrl.back()  # at b
    ctrl.back()  # at a
    ctrl.push("new")  # branch → drops b, c; now positioned at "new"
    # Forward history was truncated → nothing beyond "new".
    assert ctrl.forward() is False
    # Back returns to "a" (the only earlier entry).
    assert ctrl.back() is True
    assert view.loaded[-1] == "a"


def test_cap_evicts_oldest(monkeypatch):
    view = _make_view([str(i) for i in range(300)])
    ctrl = HistoryController(view)
    monkeypatch.setattr("Imervue.gpu_image_view.history_controller._HISTORY_MAX", 3)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    for path in ("a", "b", "c", "d", "e"):
        ctrl.push(path)
    # Cap is 3 → only c, d, e survive; two backs reach c then stop.
    assert ctrl.back() is True  # d
    assert view.loaded[-1] == "d"
    assert ctrl.back() is True  # c
    assert ctrl.back() is False


def test_navigate_skips_missing_file(monkeypatch):
    view = _make_view(["a", "b"])
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("a")
    ctrl.push("b")
    # Now make files vanish; navigating must not call load.
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    before = list(view.loaded)
    ctrl.back()
    assert view.loaded == before
