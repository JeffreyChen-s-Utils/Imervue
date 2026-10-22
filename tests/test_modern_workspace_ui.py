"""Modern navigation, scalable tool icons and constrained, scrollable workspace controls."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget, QLabel, QMainWindow, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from Imervue.gui.browser_empty_state import BrowserEmptyState
from Imervue.gui.panel_scroll import PanelScrollArea, scroll_dock_content
from Imervue.paint import tool_state as ts
from Imervue.paint.tool_bar import PaintToolBar
from Imervue.paint.tool_icons import TOOL_GLYPHS, tool_icon
from Imervue.system.modern_theme import MODERN_DARK, MODERN_LIGHT, build_palette


@pytest.mark.parametrize("tool", sorted(ts.TOOLS))
def test_every_tool_has_a_visible_scalable_icon(qapp, tool):
    assert set(TOOL_GLYPHS) == set(ts.TOOLS)
    for size in (24, 48):
        image = tool_icon(tool).pixmap(size, size).toImage()
        assert not image.isNull()
        assert any(image.pixelColor(x, y).alpha() for x in range(size) for y in range(size))


def test_existing_icons_follow_dark_and_light_palette_changes(qapp):
    icon = tool_icon("brush")
    qapp.setPalette(build_palette(MODERN_DARK))
    dark = icon.pixmap(24, 24).toImage()
    qapp.setPalette(build_palette(MODERN_LIGHT))
    light = icon.pixmap(24, 24).toImage()
    assert dark != light


@pytest.mark.parametrize("area", [Qt.ToolBarArea.LeftToolBarArea, Qt.ToolBarArea.TopToolBarArea])
@pytest.mark.parametrize("percent", [80, 100, 150])
def test_tool_palette_reflows_and_scrolls_to_every_action(qapp, monkeypatch, area, percent):
    from Imervue.system.ui_scale import apply_ui_scale
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    monkeypatch.setitem(user_setting_dict, "ui_scale_percent", percent)
    apply_ui_scale(qapp, percent)
    host = QMainWindow()
    host.setCentralWidget(QLabel("canvas"))
    bar = PaintToolBar(ts.ToolState(), host)
    host.addToolBar(area, bar)
    host.resize(400, 300)
    host.show()
    try:
        qapp.processEvents()
        buttons = {b.defaultAction(): b for b in bar.findChildren(QToolButton)
                   if b.property("paintTool")}
        assert set(buttons) == {bar.action_for(tool) for tool in ts.TOOLS}
        brush, eraser = (buttons[bar.action_for(tool)] for tool in ("brush", "eraser"))
        if area == Qt.ToolBarArea.LeftToolBarArea:
            assert brush.y() == eraser.y() and brush.x() < eraser.x()
        else:
            assert brush.x() == eraser.x() and brush.y() < eraser.y()
        for tool in ts.TOOLS:
            button = buttons[bar.action_for(tool)]
            assert button.accessibleName() and button.toolTip()
            bar._palette.ensureWidgetVisible(button)
            qapp.processEvents()
            centre = button.mapTo(bar._palette.viewport(), button.rect().center())
            assert bar._palette.viewport().rect().contains(centre)
            assert bar._palette.viewport().rect().contains(
                button.mapTo(bar._palette.viewport(), button.rect().topLeft()))
            assert bar._palette.viewport().rect().contains(
                button.mapTo(bar._palette.viewport(), button.rect().bottomRight()))
            button.click()
            assert bar._state.tool == tool
            assert bar.action_for(tool).isChecked()
        assert host.height() == 300
    finally:
        host.deleteLater()


def test_tall_dock_content_scrolls_without_enlarging_the_window(qapp):
    host = QMainWindow()
    host.setCentralWidget(QLabel("canvas"))
    dock = QDockWidget("Panel", host)
    body = QWidget()
    body.setMinimumHeight(1600)
    layout = QVBoxLayout(body)
    layout.addStretch()
    button = QPushButton("Last control")
    layout.addWidget(button)
    dock.setWidget(body)
    scroll_dock_content(dock)
    host.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    host.resize(600, 400)
    host.show()
    try:
        qapp.processEvents()
        scroll = dock.widget()
        assert isinstance(scroll, PanelScrollArea)
        assert scroll.widget() is body and host.height() == 400
        assert scroll.verticalScrollBar().maximum() > 0
        scroll.ensureWidgetVisible(button)
        qapp.processEvents()
        assert scroll.viewport().rect().contains(button.mapTo(scroll.viewport(), button.rect().center()))
        seen = []
        button.clicked.connect(lambda: seen.append(True))
        button.click()
        assert seen == [True]
        scroll_dock_content(dock)
        assert dock.widget() is scroll  # No nested scroll containers on repeated setup.
    finally:
        host.deleteLater()


def test_browse_empty_states_and_recovery_actions(qapp):
    viewer = QWidget()
    viewer.model = SimpleNamespace(images=[])
    viewer._folder_scan_active = False
    state = {"filtered": False, "folder": False}
    calls = []
    card = BrowserEmptyState(viewer, open_folder=lambda: calls.append("open"),
                             clear_filters=lambda: calls.append("clear"),
                             filter_active=lambda: state["filtered"],
                             folder_open=lambda: state["folder"])
    viewer.resize(640, 400)
    viewer.show()
    try:
        qapp.processEvents()
        assert card.isVisible() and card._clear.isHidden()
        assert card._open.property("primary") is True
        start_title = card._title.text()
        card._open.click()
        assert calls == ["open"]
        state["folder"] = True
        card.refresh()
        assert card._title.text() != start_title
        state["filtered"] = True
        card.refresh()
        assert not card._clear.isHidden()
        assert card._clear.property("primary") is True
        assert card._open.property("primary") is False
        card._clear.click()
        assert calls == ["open", "clear"]
        viewer.model.images = ["image.png"]
        viewer.update()
        qapp.processEvents()
        assert card.isHidden()
        viewer.model.images = []
        viewer._folder_scan_active = True
        card.refresh()
        assert card.isHidden()
        viewer._folder_scan_active = False
        viewer.resize(560, 350)
        qapp.processEvents()
        assert card.isVisible() and viewer.rect().contains(card.geometry())
    finally:
        viewer.deleteLater()
