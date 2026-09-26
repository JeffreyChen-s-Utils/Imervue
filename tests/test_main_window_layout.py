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
 '_dual_active': ('bool', False),
 '_filter_menu': ('QMenu',),
 '_folder_change_events': ('int', 0),
 '_folder_change_last_path': ('str', ''),
 '_folder_refresh_timer': ('QTimer', 500, True),
 '_folder_tab_shortcuts': ('list',),
 '_folder_view_sessions': ('dict',),
 '_folder_watcher': ('QFileSystemWatcher',),
 '_image_issue_dock': ('QDockWidget',),
 '_image_metadata_index': ('ImageMetadataIndex',),
 '_image_tabs': ('list',),
 '_last_screen_avail': ('NoneType', None),
 '_main_tabs': ('QTabWidget',),
 '_memory_pressure': ('MemoryPressureIndicator',),
 '_mode_action_grid': ('QAction',),
 '_mode_action_list': ('QAction',),
 '_modify_menu_action': ('QAction',),
 '_modify_splitter': ('QSplitter',),
 '_paint_page': ('QWidget',),
 '_pet_tray': ('PetTrayIcon',),
 '_plugin_menu': ('QMenu',),
 '_plugin_menu_entries': ('list',),
 '_pre_dual_mode': ('str', 'grid'),
 '_progress_bar': ('QProgressBar',),
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
 '_tree_panel': ('QWidget',),
 '_tree_watchdog': ('FileTreeWatchdog',),
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
 'pet_workspace': ('PetWorkspace',),
 'plugin_manager': ('PluginManager',),
 'puppet_workspace': ('PuppetWorkspace',),
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
