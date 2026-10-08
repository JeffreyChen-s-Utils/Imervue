"""Tests for the dock panels of the Imervue and Modify tabs.

The pure state helpers, ``CanvasHost`` and ``MainWindowDocksMixin`` run on a
small window built here: plain widgets in two dock hosts, no OpenGL viewer.
The real main window's wiring is covered in ``test_main_window_layout.py``.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QWidget

from Imervue.gui import main_window_docks as mod
from Imervue.gui.main_window_docks import (
    BROWSE_DOCK_STATE_KEY,
    MODIFY_DOCK_STATE_KEY,
    CanvasHost,
    MainWindowDocksMixin,
    add_dock,
    decode_dock_state,
    encode_dock_state,
    make_dock_host,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("blob", [b"", b"x", bytes(range(256)), b"\x00\xff" * 40])
def test_dock_state_round_trips(blob):
    assert decode_dock_state(encode_dock_state(blob)) == blob


@pytest.mark.parametrize("bad", [None, "", 5, b"bytes", ["a"], "not base64 !!", "abc"])
def test_a_missing_or_broken_state_decodes_to_nothing(bad):
    assert decode_dock_state(bad) == b""


def test_encoded_state_is_plain_ascii_for_the_settings_file():
    encoded = encode_dock_state(bytes(range(256)))
    assert isinstance(encoded, str) and encoded.isascii()


# ---------------------------------------------------------------------------
# Hosts and docks
# ---------------------------------------------------------------------------

def test_a_dock_host_is_a_widget_not_a_window(qapp):
    page = QWidget()
    host = make_dock_host()
    host.setParent(page)
    try:
        assert isinstance(host, QMainWindow)
        assert not host.isWindow()          # lives inside a tab page
        assert host.isDockNestingEnabled()
    finally:
        page.deleteLater()


def test_add_dock_names_titles_and_places_the_dock(qapp):
    host = make_dock_host()
    body = QLabel("body")
    try:
        dock = add_dock(host, "the_name", "The Title", body,
                        Qt.DockWidgetArea.RightDockWidgetArea)
        assert dock.objectName() == "the_name"
        assert dock.windowTitle() == "The Title"
        assert dock.widget() is body
        assert host.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    finally:
        host.deleteLater()


def test_dock_names_are_distinct():
    names = [mod.TREE_DOCK_NAME, mod.INFO_DOCK_NAME, mod.ISSUE_DOCK_NAME,
             mod.TOOLS_DOCK_NAME, mod.PROPERTIES_DOCK_NAME]
    assert len(set(names)) == len(names)     # restoreState matches docks by name


# ---------------------------------------------------------------------------
# CanvasHost
# ---------------------------------------------------------------------------

def test_canvas_host_starts_on_its_hint(qapp):
    host = CanvasHost("open something")
    try:
        assert host.shows_hint() and host.count() == 1
        hint = host.currentWidget()
        assert hint.text() == "open something"
        assert hint.alignment() == Qt.AlignmentFlag.AlignCenter and hint.wordWrap()
    finally:
        host.deleteLater()


def test_canvas_host_shows_the_canvas_and_the_hint_when_it_leaves(qapp):
    host = CanvasHost("hint")
    canvas = QWidget()
    try:
        host.set_canvas(canvas)
        assert host.currentWidget() is canvas and not host.shows_hint()
        canvas.setParent(None)              # how DevelopPanel detaches a canvas
        assert host.shows_hint() and host.count() == 1
    finally:
        canvas.deleteLater()
        host.deleteLater()


def test_canvas_host_shows_the_newest_canvas(qapp):
    host = CanvasHost("hint")
    first, second = QWidget(), QWidget()
    try:
        host.set_canvas(first)
        host.set_canvas(second)
        assert host.currentWidget() is second
    finally:
        host.deleteLater()


# ---------------------------------------------------------------------------
# MainWindowDocksMixin, on a window without the viewer
# ---------------------------------------------------------------------------

class _Sidebar(QLabel):
    def __init__(self):
        super().__init__("info")
        self.active_calls: list[bool] = []

    def set_active(self, active: bool) -> None:
        self.active_calls.append(active)


class _Issues(QLabel):
    def __init__(self):
        super().__init__("issues")
        self.count = 0

    def issue_count(self) -> int:
        return self.count


class _Window(MainWindowDocksMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self._main_tabs = QTabWidget()
        self.setCentralWidget(self._main_tabs)
        self._tree_panel = QLabel("tree")
        self.exif_sidebar = _Sidebar()
        self.image_issue_panel = _Issues()
        self._browse_window = make_dock_host()
        self._browse_window.setCentralWidget(QLabel("viewer"))
        self._build_browse_docks()
        self._main_tabs.addTab(self._browse_window, "Imervue")
        self._modify_window = make_dock_host()
        self._modify_window.setCentralWidget(CanvasHost("hint"))
        self._build_modify_docks(QLabel("tools"), QLabel("adjust"))
        self._main_tabs.addTab(self._modify_window, "Modify")


@pytest.fixture
def window(qapp, monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    win = _Window()
    win.resize(1200, 700)
    yield win
    win.deleteLater()


def _area(win, host, dock):
    return host.dockWidgetArea(dock)


def test_default_layout(window):
    left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
    browse, modify = window._browse_window, window._modify_window  # noqa: SLF001
    assert _area(window, browse, window._tree_dock) == left  # noqa: SLF001
    assert _area(window, browse, window._info_dock) == right  # noqa: SLF001
    assert _area(window, browse, window._image_issue_dock) == right  # noqa: SLF001
    assert _area(window, modify, window._modify_tools_dock) == left  # noqa: SLF001
    assert _area(window, modify, window._modify_properties_dock) == right  # noqa: SLF001
    assert window._image_issue_dock.isHidden()  # noqa: SLF001
    assert not window._tree_dock.isHidden() and not window._info_dock.isHidden()  # noqa: SLF001


def test_dock_titles_and_bodies(window):
    titled = {dock.windowTitle(): dock.widget()
              for _tab, docks in window.panel_docks() for dock in docks}
    assert titled == {
        "Folders": window._tree_panel,  # noqa: SLF001
        "Image Info": window.exif_sidebar,
        "Image load issues": window.image_issue_panel,
        "Tools": window._modify_tools_dock.widget(),  # noqa: SLF001
        "Adjustments": window._modify_properties_dock.widget(),  # noqa: SLF001
    }


def test_panel_docks_are_grouped_under_their_tab(window):
    groups = window.panel_docks()
    assert [title for title, _docks in groups] == ["Imervue", "Modify"]
    assert [len(docks) for _title, docks in groups] == [3, 2]


def test_the_info_panel_follows_its_docks_visibility(window, qapp):
    window.show()
    qapp.processEvents()
    try:
        assert window.exif_sidebar.active_calls[-1] is True
        window._info_dock.hide()  # noqa: SLF001
        assert window.exif_sidebar.active_calls[-1] is False
        window._info_dock.show()  # noqa: SLF001
        assert window.exif_sidebar.active_calls[-1] is True
    finally:
        window.hide()


def test_layouts_save_and_restore_through_the_settings(window):
    window._tree_dock.hide()  # noqa: SLF001
    window._modify_window.addDockWidget(  # noqa: SLF001
        Qt.DockWidgetArea.LeftDockWidgetArea, window._modify_properties_dock)  # noqa: SLF001
    window._save_dock_layouts()  # noqa: SLF001
    assert set(user_setting_dict) >= {BROWSE_DOCK_STATE_KEY, MODIFY_DOCK_STATE_KEY}

    window.reset_panel_layout()
    for key in (BROWSE_DOCK_STATE_KEY, MODIFY_DOCK_STATE_KEY):
        assert key not in user_setting_dict   # reset forgets the saved layouts
    assert not window._tree_dock.isHidden()  # noqa: SLF001

    states = window.dock_layout_states()
    window._tree_dock.hide()  # noqa: SLF001
    window.apply_dock_layout_states(states)
    assert not window._tree_dock.isHidden()  # noqa: SLF001


def test_restore_puts_a_saved_layout_back(window):
    left = Qt.DockWidgetArea.LeftDockWidgetArea
    modify = window._modify_window  # noqa: SLF001
    window._tree_dock.hide()  # noqa: SLF001
    modify.addDockWidget(left, window._modify_properties_dock)  # noqa: SLF001
    window._save_dock_layouts()  # noqa: SLF001
    saved = {key: user_setting_dict[key]
             for key in (BROWSE_DOCK_STATE_KEY, MODIFY_DOCK_STATE_KEY)}
    window.reset_panel_layout()
    user_setting_dict.update(saved)
    window._restore_dock_layouts()  # noqa: SLF001
    assert window._tree_dock.isHidden()  # noqa: SLF001
    assert modify.dockWidgetArea(window._modify_properties_dock) == left  # noqa: SLF001


@pytest.mark.parametrize("saved", [None, "", "not base64 !!", encode_dock_state(b"garbage")])
def test_a_broken_saved_layout_keeps_the_default(window, saved):
    user_setting_dict[BROWSE_DOCK_STATE_KEY] = saved
    user_setting_dict[MODIFY_DOCK_STATE_KEY] = saved
    window._restore_dock_layouts()  # noqa: SLF001
    assert not window._tree_dock.isHidden()  # noqa: SLF001
    assert window._browse_window.dockWidgetArea(window._tree_dock) == (  # noqa: SLF001
        Qt.DockWidgetArea.LeftDockWidgetArea)


def test_reset_docks_a_floating_panel_again(window):
    dock = window._info_dock  # noqa: SLF001
    dock.setFloating(True)
    dock.hide()
    window.reset_panel_layout()
    assert not dock.isFloating() and not dock.isHidden()
    assert window._browse_window.dockWidgetArea(dock) == (  # noqa: SLF001
        Qt.DockWidgetArea.RightDockWidgetArea)


@pytest.mark.parametrize(("issues", "hidden"), [(0, True), (2, False)])
def test_reset_shows_the_issue_panel_only_when_it_has_issues(window, issues, hidden):
    window.image_issue_panel.count = issues
    window._image_issue_dock.show()  # noqa: SLF001
    window.reset_panel_layout()
    assert window._image_issue_dock.isHidden() is hidden  # noqa: SLF001


def test_browse_split_widths_reports_tree_and_viewer(window, qapp):
    window.show()
    qapp.processEvents()
    try:
        tree, viewer = window.browse_split_widths()
        assert tree == window._tree_dock.width() > 0  # noqa: SLF001
        assert viewer == window._browse_window.centralWidget().width() > 0  # noqa: SLF001
    finally:
        window.hide()


def test_set_tree_dock_width_resizes_the_folder_dock(window, qapp, pump_until):
    window.show()
    qapp.processEvents()
    try:
        window.set_tree_dock_width(333)
        assert pump_until(lambda: window._tree_dock.width() == 333)  # noqa: SLF001
    finally:
        window.hide()


@pytest.mark.parametrize("width", [0, -5])
def test_a_width_of_nothing_is_ignored(window, width):
    calls = []
    window._browse_window.resizeDocks = lambda *a: calls.append(a)  # noqa: SLF001
    window.set_tree_dock_width(width)
    assert calls == []


def test_the_panels_menu_lists_every_dock_and_resets(window, monkeypatch):
    from PySide6.QtWidgets import QMenu

    from Imervue.menu import file_menu
    monkeypatch.setattr(file_menu.language_wrapper, "language_word_dict", {})
    view_menu = QMenu(window)
    file_menu._add_panel_entries(window, view_menu, {})  # noqa: SLF001
    panels = view_menu.findChild(QMenu, "view.panels")
    assert panels.title() == "Panels"
    actions = panels.actions()
    texts = [a.text() for a in actions if not a.isSeparator()]
    assert texts == ["Folders", "Image Info", "Image load issues", "Tools", "Adjustments",
                     "Reset Panel Layout"]
    sections = [a.text() for a in actions if a.isSeparator() and a.text()]
    assert sections == ["Imervue", "Modify"]

    toggle = next(a for a in actions if a.text() == "Folders")
    assert toggle.isCheckable()
    window.show()
    try:
        assert toggle.isChecked()
        toggle.trigger()
        assert window._tree_dock.isHidden()  # noqa: SLF001
        next(a for a in actions if a.text() == "Reset Panel Layout").trigger()
        assert not window._tree_dock.isHidden()  # noqa: SLF001
    finally:
        window.hide()
