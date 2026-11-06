"""Tests for ``Imervue.gui.deep_zoom_chrome``: Deep Zoom folds the panels into icon buttons.

The pure ``CollapseState`` runs without Qt; ``DeepZoomChrome`` runs on real
docks in a small ``QMainWindow`` plus a plain widget for the filter row, no
OpenGL viewer. The main window's wiring lives in ``test_main_window_layout.py``
and ``test_main_window_docks.py``.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow

from Imervue.gui import main_window_layout, main_window_views
from Imervue.gui.deep_zoom_chrome import (
    PANEL_FILTERS,
    PANEL_FOLDERS,
    PANEL_ICONS,
    PANEL_INFO,
    CollapseState,
    DeepZoomChrome,
)
from Imervue.gui.tool_icons import _WORKSPACE_GLYPHS, TOOL_GLYPHS

# ---------------------------------------------------------------------------
# CollapseState
# ---------------------------------------------------------------------------


def test_a_new_state_is_not_collapsed():
    state = CollapseState()
    assert not state.collapsed
    assert state.remembered() == {}
    assert state.expand() == {}


def test_collapse_hides_every_panel_and_remembers_them():
    state = CollapseState()
    assert state.collapse({"a": True, "b": False}) == {"a": False, "b": False}
    assert state.collapsed
    assert state.remembered() == {"a": True, "b": False}


def test_collapse_of_no_panels_still_counts_as_collapsed():
    state = CollapseState()
    assert state.collapse({}) == {}
    assert state.collapsed


def test_a_second_collapse_changes_nothing_and_keeps_the_first_snapshot():
    state = CollapseState()
    state.collapse({"a": True})
    assert state.collapse({"a": False}) == {}
    assert state.remembered() == {"a": True}


def test_expand_returns_the_snapshot_once():
    state = CollapseState()
    state.collapse({"a": True, "b": False})
    assert state.expand() == {"a": True, "b": False}
    assert not state.collapsed
    assert state.expand() == {}


def test_forget_drops_the_snapshot_without_returning_it():
    state = CollapseState()
    state.collapse({"a": True})
    state.forget()
    assert not state.collapsed
    assert state.expand() == {}


def test_remembered_is_a_copy():
    state = CollapseState()
    state.collapse({"a": True})
    state.remembered()["a"] = False
    assert state.remembered() == {"a": True}


def test_every_panel_has_a_drawn_icon():
    glyphs = TOOL_GLYPHS | _WORKSPACE_GLYPHS
    assert set(PANEL_ICONS) == {PANEL_FOLDERS, PANEL_FILTERS, PANEL_INFO}
    assert all(icon in glyphs for icon in PANEL_ICONS.values())


# ---------------------------------------------------------------------------
# DeepZoomChrome on real docks
# ---------------------------------------------------------------------------


class _Rig:
    """A dock host with Folders on the left, Image Info on the right and a filter row."""

    def __init__(self):
        self.host = QMainWindow()
        self.filters = QLabel("filters")
        self.host.setCentralWidget(self.filters)
        self.folders = QDockWidget("Folders", self.host)
        self.folders.setWidget(QLabel("tree"))
        self.host.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.folders)
        self.info = QDockWidget("Info", self.host)
        self.info.setWidget(QLabel("info"))
        self.host.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.info)
        self.wanted: bool | None = False
        self.chrome = DeepZoomChrome(
            {PANEL_FOLDERS: self.folders, PANEL_FILTERS: self.filters, PANEL_INFO: self.info},
            {PANEL_FOLDERS: "folders tip", PANEL_INFO: "info tip"},
            lambda: self.wanted)

    def shown(self) -> dict[str, bool]:
        return {PANEL_FOLDERS: not self.folders.isHidden(),
                PANEL_FILTERS: not self.filters.isHidden(),
                PANEL_INFO: not self.info.isHidden()}

    def checked(self) -> dict[str, bool]:
        return {name: button.isChecked() for name, button in self.chrome.buttons.items()}

    def buttons_shown(self) -> set[bool]:
        return {not button.isHidden() for button in self.chrome.buttons.values()}

    def enter(self):
        self.wanted = True
        self.chrome.sync()

    def leave(self):
        self.wanted = False
        self.chrome.sync()


@pytest.fixture
def rig(qapp):
    made = _Rig()
    yield made
    for button in made.chrome.buttons.values():
        button.deleteLater()
    made.chrome.deleteLater()
    made.host.deleteLater()


ALL_SHOWN = {PANEL_FOLDERS: True, PANEL_FILTERS: True, PANEL_INFO: True}
ALL_HIDDEN = {PANEL_FOLDERS: False, PANEL_FILTERS: False, PANEL_INFO: False}


def test_buttons_start_hidden_with_their_tips(rig):
    assert rig.buttons_shown() == {False}
    assert all(button.isCheckable() for button in rig.chrome.buttons.values())
    assert rig.chrome.buttons[PANEL_FOLDERS].toolTip() == "folders tip"
    assert rig.chrome.buttons[PANEL_FOLDERS].accessibleName() == "folders tip"
    assert rig.chrome.buttons[PANEL_FILTERS].toolTip() == ""   # a missing tip is empty
    assert not rig.chrome.collapsed


def test_outside_deep_zoom_nothing_changes(rig):
    rig.leave()
    assert rig.shown() == ALL_SHOWN
    assert rig.buttons_shown() == {False}


def test_entering_deep_zoom_folds_every_panel_into_buttons(rig):
    rig.enter()
    assert rig.chrome.collapsed
    assert rig.shown() == ALL_HIDDEN
    assert rig.buttons_shown() == {True}
    assert rig.checked() == ALL_HIDDEN


def test_leaving_deep_zoom_puts_the_panels_back(rig):
    rig.info.hide()   # the user had closed Image Info before
    rig.enter()
    rig.leave()
    assert not rig.chrome.collapsed
    assert rig.shown() == {PANEL_FOLDERS: True, PANEL_FILTERS: True, PANEL_INFO: False}
    assert rig.buttons_shown() == {False}


def test_a_button_brings_its_panel_back_and_hides_it_again(rig):
    rig.enter()
    rig.chrome.buttons[PANEL_FOLDERS].click()
    assert rig.shown() == {PANEL_FOLDERS: True, PANEL_FILTERS: False, PANEL_INFO: False}
    assert rig.checked()[PANEL_FOLDERS] is True
    rig.chrome.buttons[PANEL_FOLDERS].click()
    assert rig.shown() == ALL_HIDDEN
    assert rig.checked()[PANEL_FOLDERS] is False


def test_a_panel_brought_back_stays_for_the_next_image(rig):
    rig.enter()
    rig.chrome.buttons[PANEL_FILTERS].click()
    rig.enter()   # the next image of the folder: still Deep Zoom
    assert rig.shown()[PANEL_FILTERS] is True


def test_leaving_restores_the_layout_from_before_not_the_toggles(rig):
    rig.enter()
    rig.chrome.buttons[PANEL_INFO].click()
    rig.chrome.buttons[PANEL_INFO].click()
    rig.leave()
    assert rig.shown() == ALL_SHOWN


def test_closing_a_dock_by_itself_unchecks_its_button(rig, qapp):
    rig.host.show()
    qapp.processEvents()
    try:
        rig.enter()
        rig.chrome.buttons[PANEL_INFO].click()
        rig.info.close()   # its own title-bar close button
        assert rig.checked()[PANEL_INFO] is False
    finally:
        rig.host.hide()


def test_a_floating_dock_is_left_alone(rig):
    rig.folders.setFloating(True)
    rig.enter()
    assert rig.shown() == {PANEL_FOLDERS: True, PANEL_FILTERS: False, PANEL_INFO: False}
    rig.folders.hide()
    rig.leave()
    assert rig.folders.isHidden()   # not part of what Deep Zoom put back
    rig.folders.setFloating(False)


def test_none_leaves_the_panels_as_they_are(rig):
    rig.enter()
    rig.wanted = None   # theater mode owns them
    rig.chrome.sync()
    assert rig.chrome.collapsed
    assert rig.shown() == ALL_HIDDEN


def test_schedule_sync_decides_once_the_event_loop_runs(rig, pump_until):
    rig.wanted = True
    rig.chrome.schedule_sync()
    assert not rig.chrome.collapsed   # not yet
    pump_until(lambda: rig.chrome.collapsed)
    assert rig.shown() == ALL_HIDDEN


def test_uncollapsed_shows_the_old_layout_only_inside_the_block(rig):
    rig.info.hide()
    rig.enter()
    rig.chrome.buttons[PANEL_FILTERS].click()
    with rig.chrome.uncollapsed():
        assert rig.shown() == {PANEL_FOLDERS: True, PANEL_FILTERS: True, PANEL_INFO: False}
    assert rig.shown() == {PANEL_FOLDERS: False, PANEL_FILTERS: True, PANEL_INFO: False}


def test_uncollapsed_puts_the_folded_layout_back_on_error(rig):
    rig.enter()
    with pytest.raises(RuntimeError), rig.chrome.uncollapsed():
        raise RuntimeError("save failed")
    assert rig.shown() == ALL_HIDDEN


def test_uncollapsed_outside_deep_zoom_changes_nothing(rig):
    rig.info.hide()
    with rig.chrome.uncollapsed():
        assert rig.shown()[PANEL_INFO] is False
    assert rig.shown() == {PANEL_FOLDERS: True, PANEL_FILTERS: True, PANEL_INFO: False}


def test_relayout_folds_and_remembers_the_new_layout(rig):
    rig.enter()
    rig.folders.show()
    rig.info.show()   # a restored layout that shows both docks
    rig.filters.hide()
    rig.chrome.relayout()
    assert rig.shown() == ALL_HIDDEN
    rig.leave()
    assert rig.shown() == {PANEL_FOLDERS: True, PANEL_FILTERS: False, PANEL_INFO: True}


def test_relayout_outside_deep_zoom_changes_nothing(rig):
    rig.chrome.relayout()
    assert rig.shown() == ALL_SHOWN
    assert not rig.chrome.collapsed


def test_relayout_while_theater_holds_the_panels_waits(rig):
    rig.enter()
    rig.wanted = None
    rig.chrome.relayout()
    assert not rig.chrome.collapsed
    assert rig.buttons_shown() == {False}


# ---------------------------------------------------------------------------
# Main-window wiring (stub windows, no OpenGL)
# ---------------------------------------------------------------------------


def _main(*, theater=False, deep_zoom=None, path=None, loading=None, current=None):
    viewer = SimpleNamespace(deep_zoom=deep_zoom, _deep_zoom_path=path,
                             _deep_zoom_loading=loading)
    stack = SimpleNamespace(currentWidget=lambda: viewer if current is None else current)
    return SimpleNamespace(is_theater_mode=lambda: theater, viewer=viewer, _view_stack=stack)


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({}, False),
    ({"deep_zoom": object()}, True),
    ({"path": "a.png"}, True),
    ({"loading": "a.png"}, True),
    ({"path": "a.png", "current": object()}, False),   # list / dual view on top
    ({"theater": True, "path": "a.png"}, None),
    ({"theater": True}, None),
])
def test_the_window_wants_the_panels_folded_only_in_deep_zoom(kwargs, expected):
    wanted = main_window_layout.MainWindowLayoutMixin._deep_zoom_chrome_wanted
    assert wanted(_main(**kwargs)) is expected


def test_the_window_tolerates_a_viewer_without_deep_zoom_state():
    main = SimpleNamespace(is_theater_mode=lambda: False, viewer=SimpleNamespace(),
                           _view_stack=SimpleNamespace(currentWidget=lambda: None))
    assert main_window_layout.MainWindowLayoutMixin._deep_zoom_chrome_wanted(main) is False


def test_leaving_theater_mode_asks_the_chrome_to_sync():
    calls = []
    host = SimpleNamespace(
        _theater_prev_visibility=None, _theater_widgets=[],
        _deep_zoom_chrome=SimpleNamespace(schedule_sync=lambda: calls.append("sync")),
        _theater_toast=lambda *_a: calls.append("toast"))
    main_window_views.MainWindowViewsMixin._exit_theater_mode(host, [])
    assert calls == ["sync", "toast"]


def test_leaving_theater_mode_without_the_chrome_still_works():
    calls = []
    host = SimpleNamespace(_theater_prev_visibility=None, _theater_widgets=[],
                           _theater_toast=lambda *_a: calls.append("toast"))
    main_window_views.MainWindowViewsMixin._exit_theater_mode(host, [])
    assert calls == ["toast"]
