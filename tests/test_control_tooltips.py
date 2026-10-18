"""Missing help coverage, live values, existing help and late-created UI surfaces."""
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QAction, QActionGroup, QHelpEvent, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QKeySequenceEdit,
    QLabel, QLineEdit, QListWidget, QMenu, QPushButton, QRadioButton, QSlider, QSpinBox,
    QTabBar, QTableWidget, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from Imervue.gui.control_tooltips import (
    enable_control_tooltips, ensure_tooltip, fill_missing_tooltips, install_tooltips,
)
from Imervue.gui.tooltip_text import plain_label, readable_text
from Imervue.multi_language.language_wrapper import language_wrapper


@pytest.fixture(autouse=True)
def language():
    original = language_wrapper.language
    language_wrapper.reset_language("English")
    yield
    language_wrapper.reset_language(original)


def test_authored_help_survives_repeated_fills_and_custom_replacement(qapp):
    button = QPushButton("Open")
    try:
        button.setToolTip("Detailed, authored help")
        enable_control_tooltips(button)
        fill_missing_tooltips(button)
        assert button.toolTip() == "Detailed, authored help"
        button.setToolTip("")
        ensure_tooltip(button)
        assert "Open" in button.toolTip()
        button.setToolTip("Replacement help")
        ensure_tooltip(button)
        assert button.toolTip() == "Replacement help"
    finally:
        button.deleteLater()


def test_deleted_transient_controls_are_skipped_during_a_help_walk(qapp, monkeypatch):
    import shiboken6
    from Imervue.gui import control_tooltips
    button = QToolButton()

    def replaces_control(widget):
        shiboken6.delete(widget)
        return "Old control was replaced"

    monkeypatch.setattr(control_tooltips, "_widget_tip", replaces_control)
    ensure_tooltip(button)
    ensure_tooltip(button)
    assert not shiboken6.isValid(button)


def test_ranges_and_names_are_refreshed_without_exposing_entered_values(qapp):
    root = QWidget()
    form = QFormLayout(root)
    spin = QSpinBox()
    spin.setRange(-20, 80)
    spin.setSuffix(" %")
    form.addRow("&Strength:", spin)
    secret = QLineEdit()
    secret.setEchoMode(QLineEdit.EchoMode.Password)
    secret.setText("private-token-never-include")
    form.addRow("Password:", secret)
    try:
        fill_missing_tooltips(root)
        assert "Strength" in spin.toolTip() and "-20 %" in spin.toolTip()
        assert "80 %" in spin.toolTip()
        assert "private-token" not in secret.toolTip()
        assert "Password" in secret.toolTip()
        spin.setMaximum(150)
        ensure_tooltip(spin)
        assert "150 %" in spin.toolTip()
        assert "80 %" not in spin.toolTip()
    finally:
        root.deleteLater()


def test_buddies_nested_rows_and_internal_editors_share_the_correct_field_name(qapp):
    root = QWidget()
    layout = QVBoxLayout(root)
    label = QLabel("Opacity")
    row = QHBoxLayout()
    slider, spin = QSlider(Qt.Orientation.Horizontal), QSpinBox()
    row.addWidget(slider)
    row.addWidget(spin)
    layout.addWidget(label)
    layout.addLayout(row)
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItem("user-entered-private-path")
    buddy = QLabel("Colour profile")
    buddy.setBuddy(combo)
    layout.addWidget(buddy)
    layout.addWidget(combo)
    try:
        fill_missing_tooltips(root)
        for control in (slider, spin, spin.findChild(QLineEdit)):
            assert "Opacity" in control.toolTip()
        assert "Colour profile" in combo.toolTip()
        assert "user-entered-private-path" not in combo.lineEdit().toolTip()
    finally:
        root.deleteLater()


def test_grid_labels_stay_on_their_row_and_do_not_cross_another_control(qapp):
    root = QWidget()
    root.setWindowTitle("Settings")
    layout = QGridLayout(root)
    width, height, other = QSpinBox(), QSpinBox(), QLineEdit()
    layout.addWidget(QLabel("Width"), 0, 0)
    layout.addWidget(width, 0, 1)
    layout.addWidget(QLabel("Height"), 1, 0)
    layout.addWidget(height, 1, 1)
    layout.addWidget(other, 1, 2)
    try:
        fill_missing_tooltips(root)
        assert "Width" in width.toolTip() and "Height" not in width.toolTip()
        assert "Height" in height.toolTip() and "Width" not in height.toolTip()
        assert "Settings" in other.toolTip() and "Height" not in other.toolTip()
    finally:
        root.deleteLater()


def test_key_edit_and_clear_buttons_describe_the_actual_operation(qapp):
    root = QWidget()
    layout = QVBoxLayout(root)
    keys = QKeySequenceEdit()
    keys.setAccessibleName("Show pet")
    line = QLineEdit()
    line.setClearButtonEnabled(True)
    line.setText("Example")
    layout.addWidget(keys)
    layout.addWidget(line)
    try:
        fill_missing_tooltips(root)
        assert "key combination" in keys.toolTip()
        clear = line.findChild(QToolButton)
        assert "Clear this field" in clear.toolTip()
    finally:
        root.deleteLater()


def test_actions_include_live_shortcuts_and_keep_authored_descriptions(qapp):
    menu = QMenu("File")
    action = menu.addAction("&Open…")
    action.setShortcut(QKeySequence("Ctrl+O"))
    action.setStatusTip("Open an existing image")
    try:
        fill_missing_tooltips(menu)
        assert "existing image" in action.toolTip()
        assert "Ctrl+O" in action.toolTip()
        action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        ensure_tooltip(action)
        assert "Ctrl+Shift+O" in action.toolTip()
        action.setToolTip("Keep this detailed tooltip")
        fill_missing_tooltips(menu)
        assert action.toolTip() == "Keep this detailed tooltip"
        assert menu.toolTipsVisible()
    finally:
        menu.deleteLater()


def test_exclusive_choices_are_described_as_selections(qapp):
    root = QWidget()
    radio = QRadioButton("Option", root)
    group = QActionGroup(root)
    action = QAction("Choice", root)
    action.setCheckable(True)
    group.addAction(action)
    try:
        fill_missing_tooltips(root)
        assert "Select" in radio.toolTip() and "disable" not in radio.toolTip()
        assert "Select" in action.toolTip() and "disable" not in action.toolTip()
    finally:
        root.deleteLater()


def test_rich_labels_are_readable_and_literal_file_names_are_escaped(qapp):
    label = QLabel("<b>Instructions</b><br>Second line")
    action = QAction("<file>&name.png")
    path = QLabel("R&D.png")
    try:
        ensure_tooltip(label)
        ensure_tooltip(action)
        ensure_tooltip(path)
        assert readable_text(label.toolTip()) == "Instructions\nSecond line"
        assert readable_text(path.toolTip()) == "R&D.png"
        assert plain_label("&Open…") == "Open"
        assert "&lt;file&gt;name.png" in action.toolTip()
    finally:
        label.deleteLater()
        action.deleteLater()
        path.deleteLater()


def test_disabled_controls_and_late_dialogs_are_covered_by_one_filter(qapp):
    install_tooltips(qapp)
    handler = qapp._imervue_tooltip_filter
    install_tooltips(qapp)
    assert qapp._imervue_tooltip_filter is handler
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    button = QPushButton("Export")
    button.setEnabled(False)
    layout.addWidget(button)
    try:
        qapp.sendEvent(dialog, QShowEvent())
        assert "Export" in button.toolTip()
        menu = QMenu("New commands", dialog)
        action = menu.addAction("Later command")
        qapp.sendEvent(menu, QShowEvent())
        assert "Later command" in action.toolTip()
        assert menu.toolTipsVisible()
    finally:
        dialog.deleteLater()


def test_tab_tips_track_renames_and_preserve_existing_paths(qapp):
    tabs = QTabBar()
    tabs.addTab("First")
    tabs.addTab("Image")
    tabs.setTabToolTip(1, "D:/images/full-path.png")
    try:
        fill_missing_tooltips(tabs)
        assert "First" in tabs.tabToolTip(0)
        tabs.setTabText(0, "Renamed")
        fill_missing_tooltips(tabs)
        assert "Renamed" in tabs.tabToolTip(0)
        assert tabs.tabToolTip(1) == "D:/images/full-path.png"
    finally:
        tabs.deleteLater()


def test_generated_help_follows_language_changes(qapp):
    spin = QSpinBox()
    spin.setAccessibleName("Size")
    try:
        ensure_tooltip(spin)
        assert "from" in spin.toolTip()
        language_wrapper.reset_language("Traditional_Chinese")
        ensure_tooltip(spin)
        assert "範圍" in spin.toolTip()
    finally:
        spin.deleteLater()


def test_contextual_help_is_not_reused_for_an_unrelated_control(qapp):
    from Imervue.gui.image_filter_bar import ImageFilterBar
    filters = ImageFilterBar()
    form = QWidget()
    edit = QSpinBox(form)
    edit.setAccessibleName("Rating")
    try:
        fill_missing_tooltips(filters)
        ensure_tooltip(edit)
        assert "minimum star" in filters.rating.toolTip()
        assert "minimum star" not in edit.toolTip()
        assert "YYYY-MM-DD" in filters.date_from.toolTip()
    finally:
        filters.deleteLater()
        form.deleteLater()


def test_custom_curve_and_rating_surfaces_explain_their_gestures(qapp):
    from Imervue.gui.exif_sidebar import _StarLabel
    from Imervue.gui.tone_curve_dialog import _CurveCanvas
    from Imervue.paint.pressure_curve_dialog import PressureCurveEditor
    widgets = [_CurveCanvas([]), PressureCurveEditor(), _StarLabel(3, MagicMock())]
    try:
        for widget in widgets:
            ensure_tooltip(widget)
            assert widget.toolTip()
        assert "control point" in widgets[0].toolTip()
        assert "right-click" in widgets[1].toolTip()
        assert "rating" in widgets[2].toolTip()
    finally:
        for widget in widgets:
            widget.deleteLater()


def test_puppet_tip_uses_parameter_units_instead_of_internal_slider_steps(qapp):
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document import Parameter, PuppetDocument
    from Imervue.puppet.parameter_dock import ParameterDock
    canvas = PuppetCanvas()
    dock = ParameterDock(canvas)
    doc = PuppetDocument(size=(100, 100))
    doc.parameters = [Parameter(id="Angle", min=-30, max=30, default=0)]
    try:
        canvas.load_document(doc)
        slider = dock.slider_for("Angle")
        assert slider.maximum() == 1000
        assert "-30" in slider.toolTip() and "30" in slider.toolTip()
        assert "1000" not in slider.toolTip()
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_item_help_uses_display_text_without_writing_to_the_model(qapp, monkeypatch):
    view = QListWidget()
    view.addItems(["A < B & C", "Authored"])
    view.item(1).setToolTip("Keep custom item help")
    view.show()
    qapp.processEvents()
    show = MagicMock()
    monkeypatch.setattr(QToolTip, "showText", show)
    install_tooltips(qapp)
    try:
        for row in range(2):
            point = view.visualItemRect(view.item(row)).center()
            event = QHelpEvent(QEvent.Type.ToolTip, point, view.viewport().mapToGlobal(point))
            qapp.sendEvent(view.viewport(), event)
            if row == 0:
                assert show.call_count == 1
                assert "A &lt; B &amp; C" in show.call_args.args[1]
                assert view.item(0).toolTip() == ""
            else:
                assert view.item(1).toolTip() == "Keep custom item help"
    finally:
        view.deleteLater()


def test_table_header_help_preserves_native_roles(qapp, monkeypatch):
    view = QTableWidget(1, 1)
    view.setHorizontalHeaderLabels(["File name"])
    view.show()
    qapp.processEvents()
    show = MagicMock()
    monkeypatch.setattr(QToolTip, "showText", show)
    header = view.horizontalHeader()
    assert isinstance(header, QHeaderView)
    install_tooltips(qapp)
    try:
        point = QPoint(8, 8)
        qapp.sendEvent(header.viewport(), QHelpEvent(
            QEvent.Type.ToolTip, point, header.viewport().mapToGlobal(point)))
        assert "File name" in show.call_args.args[1]
    finally:
        view.deleteLater()
