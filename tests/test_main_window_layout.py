"""Characterisation test for the widgets ``ImervueMainWindow``'s constructor creates.

Pins every instance attribute on a freshly built main window: its name, its
type, and the value of flags, numbers, strings and ``None``, plus each
``QTimer``'s interval and single-shot flag. Generated before the ``_build_*``
layout methods moved to ``gui/main_window_layout.py`` (where the whole
817-widget tree was also compared once, unchanged), so a builder cannot drop,
rename or retype a widget the rest of the window relies on.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QTimer

from _qt_skip import pytestmark  # noqa: E402,F401

_EXPECTED = {'_browse_mode': ('str', 'grid'),
 '_browse_window': ('QMainWindow',),
 '_dual_active': ('bool', False),
 '_filter_menu': ('QMenu',),
 '_folder_change_events': ('int', 0),
 '_folder_change_last_path': ('str', ''),
 '_folder_refresh_timer': ('QTimer', 500, True),
 '_folder_tab_shortcuts': ('list',),
 '_folder_view_sessions': ('dict',),
 '_folder_watcher': ('FolderPoller',),
 '_follows_app_state': ('bool', True),
 '_image_issue_dock': ('QDockWidget',),
 '_image_metadata_index': ('ImageMetadataIndex',),
 '_image_tabs': ('list',),
 '_last_screen_avail': ('NoneType', None),
 '_info_dock': ('QDockWidget',),
 '_main_tabs': ('QTabWidget',),
 '_memory_pressure': ('MemoryPressureIndicator',),
 '_mode_action_grid': ('QAction',),
 '_mode_action_list': ('QAction',),
 '_modify_menu_action': ('QAction',),
 '_modify_canvas_host': ('CanvasHost',),
 '_modify_properties_dock': ('QDockWidget',),
 '_modify_tools_dock': ('QDockWidget',),
 '_modify_window': ('QMainWindow',),
 '_paint_page': ('QWidget',),
 '_pet_page': ('QWidget',),
 '_pet_tray': ('NoneType', None),
 '_plugin_menu': ('QMenu',),
 '_plugin_menu_entries': ('list',),
 '_pre_dual_mode': ('str', 'grid'),
 '_progress_bar': ('QProgressBar',),
 '_puppet_page': ('QWidget',),
 '_recent_folder_menu': ('QMenu',),
 '_recent_image_menu': ('QMenu',),
 '_recent_menu': ('QMenu',),
 '_restoring_filter_controls': ('bool', False),
 '_screen_adapt_timer': ('QTimer', 300, True),
 '_screen_signal_connected': ('bool', False),
 '_sort_menu': ('QMenu',),
 '_status_bar': ('QStatusBar',),
 '_status_info_cursor': ('QLabel',),
 '_status_info_index': ('QLabel',),
 '_status_info_label': ('QLabel',),
 '_status_info_resolution': ('QLabel',),
 '_status_info_size': ('QLabel',),
 '_status_info_zoom': ('QLabel',),
 '_status_label': ('QLabel',),
 '_tab_bar': ('QTabBar',),
 '_tab_switching': ('bool', False),
 '_tree_dock': ('QDockWidget',),
 '_tree_panel': ('QWidget',),
 '_view_stack': ('QStackedWidget',),
 'breadcrumb': ('BreadcrumbBar',),
 'clipboard_monitor': ('ClipboardMonitor',),
 'customContextMenuRequested': ('SignalInstance',),
 'date_from_filter': ('QLineEdit',),
 'date_to_filter': ('QLineEdit',),
 'destroyed': ('SignalInstance',),
 'dual_view': ('DualImageView',),
 'exif_sidebar': ('ExifSidebar',),
 'filename_label': ('QLabel',),
 'icon': ('QIcon',),
 'iconSizeChanged': ('SignalInstance',),
 'icon_path': ('WindowsPath',),
 'id': ('str', 'Imervue'),
 'image_filter': ('QLineEdit',),
 'image_issue_panel': ('ImageIssuePanel',),
 'image_list_view': ('ImageListView',),
 'language_menu': ('QMenu',),
 'language_wrapper': ('LanguageWrapper',),
 'missing_batch_button': ('QPushButton',),
 'model': ('FileTreeSortProxy',),
 'modify_panel': ('DevelopPanel',),
 'objectNameChanged': ('SignalInstance',),
 'pet_workspace': ('NoneType', None),
 'plugin_manager': ('PluginManager',),
 'puppet_workspace': ('NoneType', None),
 'rating_filter': ('QComboBox',),
 'tabifiedDockWidgetActivated': ('SignalInstance',),
 'tag_filter': ('QComboBox',),
 'toast': ('ToastManager',),
 'toolButtonStyleChanged': ('SignalInstance',),
 'tree': ('_FileTreeView',),
 'tree_search': ('QLineEdit',),
 'viewer': ('GPUImageView',),
 'windowIconChanged': ('SignalInstance',),
 'windowIconTextChanged': ('SignalInstance',),
 'windowTitleChanged': ('SignalInstance',)}


def _describe(value):
    if isinstance(value, QTimer):
        return ("QTimer", value.interval(), value.isSingleShot())
    if value is None or isinstance(value, (bool, int, float, str)):
        return (type(value).__name__, value)
    return (type(value).__name__,)


@pytest.fixture
def window(qapp):
    from Imervue.Imervue_main_window import ImervueMainWindow
    win = ImervueMainWindow()
    yield win
    win._release_for_close()  # noqa: SLF001 - stops the watchdog and tree workers
    ImervueMainWindow._live_windows.discard(win)  # noqa: SLF001
    win.deleteLater()


def test_constructed_attributes_are_unchanged(window):
    actual = {k: _describe(v) for k, v in sorted(vars(window).items()) if k != "__METAOBJECT__"}
    assert sorted(actual) == sorted(_EXPECTED)
    for name, expected in _EXPECTED.items():
        assert actual[name] == expected, name


def test_layout_builders_come_from_the_mixin():
    from Imervue.gui.main_window_layout import MainWindowLayoutMixin
    from Imervue.Imervue_main_window import ImervueMainWindow
    for name in ("_build_file_tree", "_build_viewer_column", "_build_image_tab_bar",
                 "_build_view_stack", "_build_workspace_tabs", "_build_status_bar"):
        assert getattr(ImervueMainWindow, name) is getattr(MainWindowLayoutMixin, name), name


def test_returning_to_paint_keeps_edited_layers_dirty_state_and_undo(window, tmp_path):
    import numpy as np
    from PIL import Image

    image = tmp_path / "next.png"
    Image.new("RGBA", (6, 6), "blue").save(image)
    tabs = window._main_tabs  # noqa: SLF001
    tabs.setCurrentIndex(2)
    workspace = window.paint_workspace
    workspace.load_image(np.zeros((8, 8, 4), dtype=np.uint8))
    canvas = workspace.canvas()
    document = canvas.document()
    stack = workspace._undo_stack  # noqa: SLF001
    document.add_layer(name="extra")
    document.layer_at(0).image[2, 3] = (20, 30, 40, 255)
    workspace._on_dispatcher_commit()  # noqa: SLF001
    tabs.setCurrentIndex(0)
    window.viewer.model.images = [str(image)]
    window.viewer.current_index = 0
    tabs.setCurrentIndex(2)
    assert workspace.canvas() is canvas
    assert canvas.document() is document
    assert workspace._undo_stack is stack  # noqa: SLF001
    assert document.layer_count == 2
    assert workspace._tab_dirty[canvas] is True  # noqa: SLF001
    assert workspace._tabs.tabText(0).endswith(" *")  # noqa: SLF001
    np.testing.assert_array_equal(document.layer_at(0).image[2, 3], (20, 30, 40, 255))
    assert stack.undo() is True
    np.testing.assert_array_equal(document.layer_at(0).image[2, 3], (0, 0, 0, 0))


def test_opening_viewer_image_in_paint_keeps_the_existing_dirty_tab(window, tmp_path):
    import numpy as np
    from PIL import Image

    image = tmp_path / "source.png"
    Image.new("RGBA", (10, 6), (20, 40, 60, 255)).save(image)
    workspace = window.paint_workspace
    original = workspace.canvas()
    document = original.document()
    workspace._on_dispatcher_commit()  # noqa: SLF001
    stack = workspace._undo_stack  # noqa: SLF001
    window.viewer.model.images = [str(image)]
    window.viewer.current_index = 0
    window._bind_paint_workspace_to_current_image()  # noqa: SLF001
    assert window._main_tabs.currentIndex() == 2  # noqa: SLF001
    assert workspace.tab_count() == 2
    assert workspace.canvas() is not original
    assert workspace.canvas().document().layer_at(0).image.shape == (6, 10, 4)
    np.testing.assert_array_equal(
        workspace.canvas().document().layer_at(0).image[0, 0], (20, 40, 60, 255),
    )
    workspace._tabs.setCurrentIndex(0)  # noqa: SLF001
    assert workspace.canvas() is original
    assert original.document() is document
    assert workspace._undo_stack is stack  # noqa: SLF001
    assert workspace._tab_dirty[original] is True  # noqa: SLF001


def test_first_paint_visit_does_not_decode_the_viewer_image(window, monkeypatch):
    from Imervue.gpu_image_view.images import image_loader

    def unexpected_decode(_path):
        raise AssertionError("Visiting Paint must not decode a browse image")

    monkeypatch.setattr(image_loader, "decode_image_file", unexpected_decode)
    window.viewer.model.images = ["unreadable.png"]
    window.viewer.current_index = 0
    window._main_tabs.setCurrentIndex(2)  # noqa: SLF001
    assert window.paint_workspace.tab_count() == 1
    assert window.paint_workspace.canvas().document().layer_count == 1


def test_file_tree_shows_every_format_the_viewer_opens(window):
    """The tree used to hide HEIC, AVIF, JPEG XL and video files."""
    from Imervue.image.formats import VIEWER_EXTENSIONS
    filters = set(window.model.sourceModel().nameFilters())
    assert filters == {f"*{ext}" for ext in VIEWER_EXTENSIONS}



def test_the_modify_panel_undoes_through_the_viewers_stack(window):
    """Slider edits are pushed to the viewer's undo manager; the panel's buttons must step it."""
    assert window.modify_panel.undo_stack() is window.viewer.undo_manager


def test_the_paint_tab_is_built_on_first_use(window):
    """Building Paint cost every launch about 0.4 s, for a tab many sessions never open."""
    tabs = window._main_tabs  # noqa: SLF001
    page = window._paint_page  # noqa: SLF001
    assert window._paint is None  # noqa: SLF001
    assert tabs.widget(tabs.indexOf(page)) is page
    tabs.setCurrentIndex(tabs.indexOf(page))
    workspace = window._paint  # noqa: SLF001
    assert type(workspace).__name__ == "PaintWorkspace"
    assert workspace.parent() is page
    assert window.paint_workspace is workspace   # built once, then reused


def test_asking_for_the_workspace_builds_it(window):
    assert type(window.paint_workspace).__name__ == "PaintWorkspace"
    assert window._paint_page.layout().indexOf(window.paint_workspace) == 0  # noqa: SLF001


def test_a_crashed_paint_session_still_gets_its_recovery_offer_at_launch(qapp, monkeypatch):
    """The autosave toast is raised while Paint is built, so pending autosaves build it at once."""
    from Imervue.gui import main_window_layout
    from Imervue.Imervue_main_window import ImervueMainWindow
    monkeypatch.setattr(main_window_layout, "_paint_autosaves_pending", lambda: True)
    win = ImervueMainWindow()
    try:
        assert type(win._paint).__name__ == "PaintWorkspace"  # noqa: SLF001
    finally:
        win._release_for_close()  # noqa: SLF001
        ImervueMainWindow._live_windows.discard(win)  # noqa: SLF001
        win.deleteLater()


def test_pending_autosaves_are_read_from_the_paint_autosave_folder(monkeypatch):
    from Imervue.gui import main_window_layout
    from Imervue.paint import auto_save
    monkeypatch.setattr(auto_save, "pending_recovery_snapshots", lambda: ["snap"])
    assert main_window_layout._paint_autosaves_pending() is True  # noqa: SLF001
    monkeypatch.setattr(auto_save, "pending_recovery_snapshots", lambda: [])
    assert main_window_layout._paint_autosaves_pending() is False  # noqa: SLF001

    def unreadable():
        raise OSError("denied")

    monkeypatch.setattr(auto_save, "pending_recovery_snapshots", unreadable)
    assert main_window_layout._paint_autosaves_pending() is False  # noqa: SLF001


def test_a_saved_workspace_records_the_tree_and_viewer_split(window):
    """A workspace keeps the folder | viewer widths, and both tabs' dock layouts."""
    from Imervue.gui.workspace_dialog import capture_current_workspace
    saved = capture_current_workspace(window, "narrow tree")
    assert saved.splitter_sizes == window.browse_split_widths()
    assert len(saved.splitter_sizes) == 2
    assert saved.browse_state_b64 and saved.modify_state_b64


def test_a_workspace_restores_the_dock_layout(window):
    from Imervue.gui.workspace_dialog import apply_workspace, capture_current_workspace
    window._tree_dock.hide()  # noqa: SLF001
    saved = capture_current_workspace(window, "no tree")
    window.reset_panel_layout()
    assert not window._tree_dock.isHidden()  # noqa: SLF001
    apply_workspace(window, saved)
    assert window._tree_dock.isHidden()  # noqa: SLF001


# ---------------------------------------------------------------------------
# Docks of the Imervue and Modify tabs
# ---------------------------------------------------------------------------

def test_the_two_tabs_are_dock_hosts_with_their_panels(window):
    from PySide6.QtCore import Qt
    tabs = window._main_tabs  # noqa: SLF001
    browse, modify = window._browse_window, window._modify_window  # noqa: SLF001
    assert tabs.widget(0) is browse and tabs.widget(1) is modify
    left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
    assert window._tree_dock.widget() is window._tree_panel  # noqa: SLF001
    assert window._info_dock.widget() is window.exif_sidebar  # noqa: SLF001
    assert window._image_issue_dock.widget() is window.image_issue_panel  # noqa: SLF001
    assert browse.dockWidgetArea(window._tree_dock) == left  # noqa: SLF001
    assert browse.dockWidgetArea(window._info_dock) == right  # noqa: SLF001
    assert modify.dockWidgetArea(window._modify_tools_dock) == left  # noqa: SLF001
    assert modify.dockWidgetArea(window._modify_properties_dock) == right  # noqa: SLF001
    assert modify.centralWidget() is window._modify_canvas_host  # noqa: SLF001
    assert window._image_issue_dock.isHidden()  # noqa: SLF001
    # The outer window has no dock of its own left: every panel belongs to a tab.
    from PySide6.QtWidgets import QDockWidget
    assert all(d.parent() is not window for d in window.findChildren(QDockWidget)
               if d in (window._tree_dock, window._info_dock,  # noqa: SLF001
                        window._image_issue_dock))  # noqa: SLF001


def test_the_viewer_column_is_the_centre_of_the_imervue_tab(window):
    centre = window._browse_window.centralWidget()  # noqa: SLF001
    assert centre.isAncestorOf(window.viewer)
    assert centre.isAncestorOf(window.breadcrumb)
    assert not centre.isAncestorOf(window.exif_sidebar)


def test_the_view_menu_has_the_panels_entries(window):
    from PySide6.QtWidgets import QMenu
    panels = window.findChild(QMenu, "view.panels")
    texts = [a.text() for a in panels.actions() if not a.isSeparator()]
    assert texts[:5] == [d.windowTitle() for _tab, docks in window.panel_docks() for d in docks]
    assert len(texts) == 6


def test_theater_mode_hides_and_restores_the_docks(window):
    window.show()
    try:
        window._info_dock.hide()  # noqa: SLF001
        window.toggle_theater_mode()
        assert window._tree_dock.isHidden() and window._info_dock.isHidden()  # noqa: SLF001
        window.toggle_theater_mode()
        assert not window._tree_dock.isHidden()  # noqa: SLF001
        assert window._info_dock.isHidden()      # was hidden before  # noqa: SLF001
    finally:
        window.hide()


def test_opening_modify_puts_the_canvas_in_the_centre(window, tmp_path):
    from PIL import Image
    image = tmp_path / "pic.png"
    Image.new("RGB", (16, 12), "red").save(image)
    host = window._modify_canvas_host  # noqa: SLF001
    assert host.shows_hint()
    window.viewer.model.images = [str(image)]
    window.viewer.current_index = 0
    window._main_tabs.setCurrentIndex(1)  # noqa: SLF001
    assert host.currentWidget() is window.modify_panel.canvas()
    window.modify_panel.bind_to_path(None)
    assert host.shows_hint()


def test_the_dock_layout_is_saved_on_close_and_restored_at_launch(window, qapp):
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gui.main_window_docks import BROWSE_DOCK_STATE_KEY
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    window._tree_dock.hide()  # noqa: SLF001
    window._save_dock_layouts()  # noqa: SLF001
    assert user_setting_dict[BROWSE_DOCK_STATE_KEY]
    second = ImervueMainWindow()
    try:
        assert second._tree_dock.isHidden()  # noqa: SLF001
    finally:
        second._release_for_close()  # noqa: SLF001
        ImervueMainWindow._live_windows.discard(second)  # noqa: SLF001
        second.deleteLater()


# ---------------------------------------------------------------------------
# Optional tabs: Puppet and Desktop Pet
# ---------------------------------------------------------------------------

def _tab_titles(win):
    tabs = win._main_tabs  # noqa: SLF001
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_the_puppet_and_pet_tabs_are_built_on_first_use(window):
    tabs = window._main_tabs  # noqa: SLF001
    for page_name, attribute, kind in (("_puppet_page", "puppet_workspace", "PuppetWorkspace"),
                                       ("_pet_page", "pet_workspace", "PetWorkspace")):
        page = getattr(window, page_name)
        assert getattr(window, attribute) is None
        tabs.setCurrentIndex(tabs.indexOf(page))
        workspace = getattr(window, attribute)
        assert type(workspace).__name__ == kind
        assert workspace.parent() is page
        tabs.setCurrentIndex(0)
        tabs.setCurrentIndex(tabs.indexOf(page))
        assert getattr(window, attribute) is workspace      # built once


def test_the_plugins_hear_of_a_pet_built_later(window):
    assert window.plugin_manager._pet_hook_connected is False  # noqa: SLF001
    tabs = window._main_tabs  # noqa: SLF001
    tabs.setCurrentIndex(tabs.indexOf(window._pet_page))  # noqa: SLF001
    assert window.plugin_manager._pet_hook_connected is True  # noqa: SLF001


def _build_window(**settings):
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.update(settings)
    return ImervueMainWindow()


def _close(win):
    from Imervue.Imervue_main_window import ImervueMainWindow
    win._release_for_close()  # noqa: SLF001
    ImervueMainWindow._live_windows.discard(win)  # noqa: SLF001
    win.deleteLater()


@pytest.mark.parametrize(("settings", "missing"), [
    ({"puppet_tab_enabled": False}, "Puppet"),
    ({"desktop_pet_tab_enabled": False}, "Desktop Pet"),
])
def test_a_tab_turned_off_is_not_added(qapp, settings, missing):
    win = _build_window(**settings)
    try:
        titles = _tab_titles(win)
        assert missing not in titles
        assert len(titles) == 4
        assert win._main_tabs.widget(2) is win._paint_page  # noqa: SLF001
    finally:
        _close(win)


def test_both_tabs_off_leave_the_three_core_tabs(qapp):
    win = _build_window(puppet_tab_enabled=False, desktop_pet_tab_enabled=False)
    try:
        assert win._main_tabs.count() == 3  # noqa: SLF001
        assert win._puppet_page is None and win._pet_page is None  # noqa: SLF001
        win._main_tabs.setCurrentIndex(2)  # noqa: SLF001
        assert win.puppet_workspace is None and win.pet_workspace is None
    finally:
        _close(win)


def test_a_pet_that_shows_on_launch_is_built_at_startup(qapp, monkeypatch):
    from Imervue.gui import optional_tabs
    monkeypatch.setattr(optional_tabs, "pet_shows_on_launch", lambda: True)
    win = _build_window()
    try:
        assert type(win.pet_workspace).__name__ == "PetWorkspace"
        assert win.puppet_workspace is None
    finally:
        _close(win)


def test_the_folder_tree_holds_no_change_notification_handles(window):
    """A watched folder's parents cannot be renamed on Windows, so the tree's model does not watch."""
    from PySide6.QtWidgets import QFileSystemModel
    source = window.model.sourceModel()
    assert source.testOption(QFileSystemModel.Option.DontWatchForChanges)
