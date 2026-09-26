"""Characterisation tests for ``ImervueMainWindow.closeEvent``'s shutdown sequence.

The real window is a GL widget no test builds, and the last-window path ends in
``os._exit``. So ``closeEvent``'s code is re-bound to a stand-in class, which
makes its zero-argument ``super()`` land on a recording base, while every
collaborator it touches records its calls into one log and ``os._exit`` is
patched to record instead of exiting. That pins the order of every shutdown
step, which steps a failure skips, and the difference between closing the last
window and a secondary one.
"""
from __future__ import annotations

import os
import types

import pytest

from Imervue import Imervue_main_window as mod
from Imervue.Imervue_main_window import ImervueMainWindow


class _Rec:
    """Records ``path`` when called; attribute access yields a child recorder."""

    def __init__(self, log: list, path: str, failing: set):
        self._log, self._path, self._failing = log, path, failing

    def __getattr__(self, name):
        return _Rec(self._log, f"{self._path}.{name}", self._failing)

    def __call__(self, *_args, **_kwargs):
        self._log.append(self._path)
        if self._path in self._failing:
            raise RuntimeError(self._path)


class _Base:
    def closeEvent(self, _event):  # noqa: N802 - Qt naming
        self._log.append("super.closeEvent")


class _Window(_Base):
    """Stand-in for the window: recorders for collaborators, real helper methods."""

    def __init__(self, log, failing, *, watchdog=True):
        self._log = log
        for name in ("_save_current_folder_session", "_main_tabs", "tree", "modify_panel",
                     "viewer", "_save_window_geometry", "plugin_manager", "deleteLater"):
            setattr(self, name, _Rec(log, name, failing))
        if watchdog:
            self._tree_watchdog = _Rec(log, "_tree_watchdog", failing)
        self._on_main_tab_changed = object()

    def __getattr__(self, name):
        attr = getattr(ImervueMainWindow, name)
        if isinstance(attr, types.FunctionType):
            return types.MethodType(attr, self)
        raise AttributeError(name)


def _close(window, event):
    fn = ImervueMainWindow.closeEvent
    assert fn.__code__.co_freevars == ("__class__",)
    rebound = types.FunctionType(fn.__code__, fn.__globals__, fn.__name__, fn.__defaults__,
                                 (types.CellType(_Window),))
    rebound(window, event)


@pytest.fixture
def run(monkeypatch):
    def _run(*, last=True, failing=(), watchdog=True):
        log: list[str] = []
        fail = set(failing)
        for name in ("cancel_pending_save", "write_user_setting", "commit_pending_deletions",
                     "offer_permanent_delete"):
            monkeypatch.setattr(mod, name, _Rec(log, name, fail))
        monkeypatch.setattr(mod, "_other_live_windows_remain", lambda _live, _me: not last)
        monkeypatch.setattr(os, "_exit", lambda code: log.append(f"os._exit({code})"))
        window = _Window(log, fail, watchdog=watchdog)
        _close(window, _Rec(log, "event", fail))
        assert window not in ImervueMainWindow._live_windows  # noqa: SLF001
        return log
    return _run


_TEARDOWN = [
    "_save_current_folder_session",
    "_main_tabs.currentChanged.disconnect",
    "_tree_watchdog.stop",
    "tree.shutdown",
    "modify_panel._debounce.stop",
    "modify_panel.recipe_committed.disconnect",
    "modify_panel._destroy_canvas",
    "modify_panel._undo_stack.clear",
    "viewer.makeCurrent",
    "viewer._delete_all_tile_textures",
    "viewer._clear_deep_zoom",
    "viewer.doneCurrent",
    "_save_window_geometry",
    "cancel_pending_save",
    "write_user_setting",
    "commit_pending_deletions",
    "offer_permanent_delete",
]


def test_last_window_runs_the_app_teardown_and_exits(run):
    assert run(last=True) == _TEARDOWN + [
        "plugin_manager.dispatch_app_closing", "plugin_manager.unload_all",
        "event.accept", "super.closeEvent", "os._exit(0)"]


def test_secondary_window_only_closes_itself(run):
    assert run(last=False) == _TEARDOWN + ["event.accept", "super.closeEvent", "deleteLater"]


def test_no_watchdog_skips_its_step(run):
    assert "_tree_watchdog.stop" not in run(watchdog=False)


def test_a_failing_step_skips_only_the_rest_of_its_group(run):
    failing = {"_save_current_folder_session", "tree.shutdown", "modify_panel._debounce.stop",
               "viewer.makeCurrent", "write_user_setting", "plugin_manager.dispatch_app_closing"}
    log = run(failing=failing)
    # Grouped steps after a failure in the same group are skipped ...
    for skipped in ("modify_panel.recipe_committed.disconnect",
                    "viewer._delete_all_tile_textures", "viewer._clear_deep_zoom",
                    "viewer.doneCurrent", "plugin_manager.unload_all"):
        assert skipped not in log
    # ... every other step still runs, in order, and the process still exits.
    assert log == [s for s in _TEARDOWN if s not in {
        "modify_panel.recipe_committed.disconnect", "viewer._delete_all_tile_textures",
        "viewer._clear_deep_zoom", "viewer.doneCurrent"}] + [
        "plugin_manager.dispatch_app_closing", "event.accept", "super.closeEvent", "os._exit(0)"]


def test_failing_steps_are_logged_with_their_names(run, caplog):
    with caplog.at_level("DEBUG", logger="Imervue"):
        run(failing={"tree.shutdown", "write_user_setting"})
    logged = [(r.levelname, r.getMessage(), r.exc_info[0] if r.exc_info else None)
              for r in caplog.records if "Best-effort" in r.getMessage()]
    assert logged == [
        ("WARNING", "Best-effort step failed: stop the file-tree workers", RuntimeError),
        ("WARNING", "Best-effort step failed: write the user settings", RuntimeError),
    ]



class _Paint:
    def __init__(self, log, answer):
        self._log, self._answer = log, answer

    def confirm_close(self):
        self._log.append("_paint.confirm_close")
        return self._answer


def test_cancelling_paints_unsaved_prompt_keeps_the_window_open(run, monkeypatch):
    """Closing Imervue never asked about Paint's unsaved tabs and ended in os._exit."""
    log: list[str] = []
    monkeypatch.setattr(os, "_exit", lambda code: log.append(f"os._exit({code})"))
    window = _Window(log, set())
    window._paint = _Paint(log, answer=False)  # noqa: SLF001
    _close(window, _Rec(log, "event", set()))
    assert log == ["_paint.confirm_close", "event.ignore"]


def test_paint_agreeing_lets_the_close_go_on(run, monkeypatch):
    log: list[str] = []
    for name in ("cancel_pending_save", "write_user_setting", "commit_pending_deletions",
                 "offer_permanent_delete"):
        monkeypatch.setattr(mod, name, _Rec(log, name, set()))
    monkeypatch.setattr(mod, "_other_live_windows_remain", lambda _live, _me: False)
    monkeypatch.setattr(os, "_exit", lambda code: log.append(f"os._exit({code})"))
    window = _Window(log, set())
    window._paint = _Paint(log, answer=True)  # noqa: SLF001
    _close(window, _Rec(log, "event", set()))
    assert log[0] == "_paint.confirm_close"
    assert log[1:] == _TEARDOWN + [
        "plugin_manager.dispatch_app_closing", "plugin_manager.unload_all",
        "event.accept", "super.closeEvent", "os._exit(0)"]
