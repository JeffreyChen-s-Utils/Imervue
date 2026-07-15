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


def _make_view(images, *, main_window=None):
    view = SimpleNamespace(
        model=_FakeModel(images),
        current_index=0,
        tile_grid_mode=False,
        loaded=[],
        events=[],
        main_window=main_window,
    )
    view._save_view_state = lambda: view.events.append("save")
    view._clear_deep_zoom = lambda: view.events.append("clear")

    def _load(p):
        view.loaded.append(p)
        view.events.append("load")

    view.load_deep_zoom_image = _load
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


def test_in_folder_navigate_saves_outgoing_view_before_clearing(monkeypatch):
    # _clear_deep_zoom nulls the save key, so the outgoing image's zoom/pan must
    # be saved first — Alt+Left then Alt+Right should return to where you left off.
    view = _make_view(["a", "b"])
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("a")
    ctrl.push("b")
    view.events.clear()
    ctrl.back()  # -> "a", still in the folder
    assert view.events[:2] == ["save", "clear"]
    assert view.events[-1] == "load"


def test_in_folder_back_loads_directly_without_reopening(monkeypatch):
    # The target is still a row in the current folder → load it in place; the
    # main window's folder-reopen path must NOT be used.
    reopened: list[str] = []
    main_window = SimpleNamespace(navigate_to_path=reopened.append)
    view = _make_view(["a", "b"], main_window=main_window)
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("a")
    ctrl.push("b")
    ctrl.back()
    assert view.loaded[-1] == "a"      # direct in-folder load
    assert view.current_index == 0
    assert reopened == []              # no folder reopen


def test_cross_folder_back_reopens_via_main_window(monkeypatch):
    # Going back reaches an image from a folder we left, so it isn't a row in
    # the current list. Loading it directly would strand a "Loading…" view the
    # completion guard discards, so it must route through the main window to
    # reopen its folder in context. (back() targets the *earlier* entry, so the
    # cross-folder image is pushed first, then the current-folder one.)
    reopened: list[str] = []
    main_window = SimpleNamespace(navigate_to_path=reopened.append)
    view = _make_view(["cur1.png", "cur2.png"], main_window=main_window)
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("/other/away.png")       # viewed while in another folder
    ctrl.push("cur1.png")              # back in the current folder
    ctrl.back()                        # → /other/away.png (not in this list)
    assert reopened == ["/other/away.png"]  # reopened in its folder
    assert view.loaded == []                # not loaded directly


def test_cross_folder_back_falls_back_to_direct_load_without_main_window(monkeypatch):
    # A detached view (no main window) can't reopen a folder — keep the previous
    # direct-load behaviour so the controller stays usable in isolation.
    view = _make_view(["cur1.png", "cur2.png"])  # main_window defaults to None
    ctrl = HistoryController(view)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("/other/away.png")
    ctrl.push("cur1.png")
    ctrl.back()
    assert view.loaded[-1] == "/other/away.png"


def test_cross_folder_reopen_is_not_re_pushed_to_history(monkeypatch):
    # Reopening through the main window ends up calling load_deep_zoom_image,
    # which pushes history — the navigating flag must suppress that so back/
    # forward don't corrupt the stack. Simulate the main window pushing back.
    view = _make_view(["cur.png"])
    ctrl = HistoryController(view)

    def _reopen(path):
        # Mirror the real flow: reopening loads the image, which re-pushes.
        ctrl.push(path)

    view.main_window = SimpleNamespace(navigate_to_path=_reopen)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    ctrl.push("/other/away.png")
    ctrl.push("cur.png")
    length_before = len(ctrl._history)
    ctrl.back()                        # → /other/away.png → reopen → re-push
    # The reopen's push happened while navigating → suppressed, stack unchanged.
    assert len(ctrl._history) == length_before
