"""Functional coverage for the modern Modify, Puppet and Desktop Pet surfaces."""
from unittest.mock import MagicMock

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QToolButton

from Imervue.gui.panel_scroll import PanelScrollArea, scroll_dock_content
from Imervue.system.ui_scale import scaled_px

from _qt_skip import pytestmark  # noqa: F401


@pytest.fixture(params=[100, 150])
def scale(qapp, monkeypatch, request):
    from Imervue.system.ui_scale import apply_ui_scale
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    font, palette, stylesheet = qapp.font(), qapp.palette(), qapp.styleSheet()
    monkeypatch.setitem(user_setting_dict, "ui_scale_percent", request.param)
    apply_ui_scale(qapp, request.param)
    yield request.param
    qapp.setFont(font)
    qapp.setPalette(palette)
    qapp.setStyleSheet(stylesheet)


def test_modify_tool_selection_opens_properties_without_losing_adjustments(qapp, scale):
    from Imervue.gui.develop_panel import DevelopPanel
    panel = DevelopPanel(MagicMock())
    left, right = panel.build_left_panel(), panel.build_right_panel()
    try:
        right.resize(right.minimumWidth(), scaled_px(520))
        right.show()
        qapp.processEvents()
        assert right.verticalScrollBar().maximum() == 0
        panel._exposure.setValue(25)
        panel._tool_buttons["text"].click()
        assert panel._property_tabs.currentIndex() == 1
        assert panel._tool_buttons["text"].isChecked()
        assert panel._exposure.value() == 25
        assert not panel._advanced_toggle.isChecked()
        panel._property_tabs.setCurrentIndex(0)
        panel._advanced_toggle.click()
        assert not panel._adv_sliders["temperature"].parentWidget().isHidden()
        for button in panel._tool_buttons.values():
            assert button.accessibleName() and button.toolTip()
            assert not button.icon().isNull()
        buttons = list(panel._tool_buttons.values())
        left.resize(left.minimumWidth(), scaled_px(350))
        left.show()
        qapp.processEvents()
        assert buttons[0].y() == buttons[1].y() and buttons[0].x() < buttons[1].x()
    finally:
        left.deleteLater()
        right.deleteLater()
        panel.deleteLater()


def test_modify_welcome_routes_back_to_browse(qapp):
    from Imervue.gui.main_window_docks import CanvasHost
    browse = MagicMock()
    host = CanvasHost("Pick an image", on_browse=browse)
    try:
        host.findChild(QPushButton).click()
        browse.assert_called_once()
        assert host.shows_hint()
    finally:
        host.deleteLater()


def test_existing_scroll_area_is_not_nested_in_another_scroll_area(qapp):
    from PySide6.QtWidgets import QDockWidget
    dock = QDockWidget()
    scroll = QScrollArea()
    dock.setWidget(scroll)
    try:
        scroll_dock_content(dock)
        assert dock.widget() is scroll
    finally:
        dock.deleteLater()


def test_pet_categories_scroll_to_every_last_control_without_creating_overlay(qapp, scale):
    from Imervue.desktop_pet.pet_workspace import PetWorkspace
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict["desktop_pet"] = {}
    workspace = PetWorkspace()
    workspace.resize(950, 650)
    workspace.show()
    try:
        tabs = workspace._settings_tabs
        assert tabs.count() == 4
        last_controls = (workspace._snap_spin, workspace._webcam_check,
                         workspace._reset_script_button, list(workspace._hotkey_edits.values())[-1])
        for index, control in enumerate(last_controls):
            tabs.setCurrentIndex(index)
            scroll = tabs.widget(index)
            assert isinstance(scroll, PanelScrollArea)
            scroll.ensureWidgetVisible(control)
            qapp.processEvents()
            centre = control.mapTo(scroll.viewport(), control.rect().center())
            assert scroll.viewport().rect().contains(centre)
        assert workspace.size().toTuple() == (950, 650)
        assert workspace.pet_window() is None
    finally:
        workspace.deleteLater()


def test_puppet_loaded_inspector_and_transport_remain_usable(qapp, scale):
    from Imervue.puppet.document import Parameter, PuppetDocument
    from Imervue.puppet.workspace import PuppetWorkspace
    workspace = PuppetWorkspace()
    workspace.resize(1280, 800)
    workspace.show()
    QTest.qWait(250)
    try:
        assert workspace._welcome.isVisible()
        assert workspace._motion_dock.isHidden()
        doc = PuppetDocument(size=(100, 100))
        doc.parameters = [Parameter(id="ParamVeryLongParameterName", min=-1, max=1, default=0)]
        workspace.canvas().load_document(doc)
        QTest.qWait(300)
        assert workspace._welcome.isHidden()
        assert workspace._motion_dock.isVisible()
        slider = workspace.parameter_dock().slider_for(doc.parameters[0].id)
        name = next(label for label in slider.parentWidget().findChildren(QLabel)
                    if label.text() == doc.parameters[0].id)
        assert slider.y() >= name.y() + name.height()
        assert slider.width() >= scaled_px(200)
        slider.setValue(slider.maximum())
        assert workspace.canvas().parameter_values()[doc.parameters[0].id] == 1
        play = workspace._motion_dock._play_btn
        assert workspace._motion_dock.rect().contains(play.mapTo(
            workspace._motion_dock, play.rect().center()))
        live = workspace.findChild(QToolButton, "puppetLiveMenu")
        assert workspace._webcam_toggle in live.menu().actions()
        workspace._blink_toggle.trigger()
        assert "1" in live.text()
        workspace._blink_toggle.trigger()
        assert "1" not in live.text()
        assert workspace.size().toTuple() == (1280, 800)
        workspace._motion_dock.hide()
        workspace.canvas().load_document(doc)
        assert workspace._motion_dock.isHidden()
    finally:
        workspace.close()
        workspace.deleteLater()
