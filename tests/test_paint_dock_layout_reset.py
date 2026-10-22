"""Reset recovers floating Paint panels and their tab groups without a GL canvas."""
from base64 import b64encode

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow, QToolBar

from Imervue.paint.workspace_docks import DockLayoutMixin
from Imervue.user_settings.user_setting_dict import user_setting_dict


class DockWindow(DockLayoutMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setCentralWidget(QLabel("canvas"))
        self._dock_clusters = {}
        for name, count in (("drawing", 4), ("canvas", 6), ("library", 4)):
            docks = []
            for index in range(count):
                dock = QDockWidget(f"{name} {index}", self)
                dock.setObjectName(f"{name}_{index}")
                dock.setWidget(QLabel("panel"))
                docks.append(dock)
            self._dock_clusters[name] = tuple(docks)
        self._install_dock_clusters(tuple(self._dock_clusters.values()))


@pytest.fixture
def window(qapp):
    widget = DockWindow()
    widget.show()
    qapp.processEvents()
    yield widget
    widget.deleteLater()


def _assert_default_groups(window):
    QApplication.processEvents()
    docks = window._ordered_docks(window._dock_clusters)
    anchor, *others = docks
    assert set(window.tabifiedDockWidgets(anchor)) == set(others)
    assert all(not dock.isFloating() and not dock.isHidden() for dock in docks)


def test_reset_redocks_floating_panels_into_one_inspector(window):
    for group in window._dock_clusters.values():
        for dock in group[:2]:
            dock.setFloating(True)
        group[-1].hide()
    assert any(dock.isFloating() for dock in window._ordered_docks(window._dock_clusters))
    window.reset_workspace_layout()
    _assert_default_groups(window)


def test_reset_recovers_a_restored_floating_layout(window, monkeypatch):
    window._dock_clusters["drawing"][0].setFloating(True)
    encoded = b64encode(bytes(window.saveState())).decode("ascii")
    monkeypatch.setitem(user_setting_dict, window.DOCK_STATE_SETTING_KEY, encoded)
    window._restore_dock_state()
    assert window._dock_clusters["drawing"][0].isFloating()
    window.reset_workspace_layout()
    assert window.DOCK_STATE_SETTING_KEY not in user_setting_dict
    _assert_default_groups(window)


def test_reset_clears_the_previous_tab_key_visibility_snapshot(window):
    window._dock_clusters["drawing"][-1].hide()
    assert window.toggle_all_docks() is False
    window.reset_workspace_layout()
    _assert_default_groups(window)
    assert window.toggle_all_docks() is False
    assert all(dock.isHidden() for dock in window._ordered_docks(window._dock_clusters))
    assert window.toggle_all_docks() is True
    _assert_default_groups(window)


@pytest.mark.parametrize("floating", [False, True])
def test_reset_restores_moved_or_floating_tools_to_the_left(window, floating):
    bar = QToolBar("Tools", window)
    bar.setObjectName("paint_toolbar_tools")
    bar.addAction("Brush")
    window._tool_bar = bar
    window.addToolBar(Qt.ToolBarArea.RightToolBarArea, bar)
    if floating:
        bar.setParent(window, Qt.WindowType.Tool)
        bar.show()
        assert bar.isFloating()
    window.reset_workspace_layout()
    QApplication.processEvents()
    assert not bar.isFloating()
    assert window.toolBarArea(bar) == Qt.ToolBarArea.LeftToolBarArea
    assert bar.orientation() == Qt.Orientation.Vertical
    assert not bar.isHidden()
