"""Pin the exact generated help for each control kind and the event filter's answers."""
from unittest.mock import MagicMock

import pytest
import shiboken6
from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import (
    QAction, QActionGroup, QHelpEvent, QKeySequence, QShowEvent, QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDockWidget, QDoubleSpinBox, QFrame, QKeySequenceEdit,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QScrollBar, QSlider, QSpinBox, QSplitter, QTabBar,
    QTableView, QTableWidget, QTextEdit, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from Imervue.gui import control_tooltips
from Imervue.gui.control_tooltips import action_tip, ensure_tooltip, fill_missing_tooltips
from Imervue.multi_language.language_wrapper import language_wrapper

NAME = "Zorbix"
RUN = "Run “Zorbix”."
TOGGLE = "Enable or disable “Zorbix”."
SELECT = "Select “Zorbix”."
EDIT = "Edit “Zorbix”."
KEYS = "Zorbix: press the desired key combination to set this shortcut."


@pytest.fixture(autouse=True)
def language():
    original = language_wrapper.language
    language_wrapper.reset_language("English")
    yield
    language_wrapper.reset_language(original)


@pytest.fixture
def owned():
    """Collect created Qt objects and delete them after the test."""
    objects = []
    yield objects
    for obj in reversed(objects):
        if shiboken6.isValid(obj):
            shiboken6.delete(obj)


def _named(widget, name=NAME):
    widget.setAccessibleName(name)
    return widget


def _checkable_button():
    button = QPushButton(NAME)
    button.setCheckable(True)
    return button


def _described_button():
    button = QPushButton(NAME)
    button.setAccessibleDescription("Custom description.")
    return button


def _child_button(parent_type):
    parent = parent_type()
    return QToolButton(parent), parent


def _spin():
    spin = _named(QSpinBox())
    spin.setRange(-5, 9)
    spin.setSuffix(" px")
    return spin


def _double_spin():
    spin = _named(QDoubleSpinBox())
    spin.setRange(0.5, 2.5)
    return spin


def _slider():
    slider = _named(QSlider(Qt.Orientation.Horizontal))
    slider.setRange(0, 99)
    return slider


def _combo(editable):
    combo = _named(QComboBox())
    combo.setEditable(editable)
    combo.addItem("private-entry")
    return combo


def _dock(features):
    dock = QDockWidget(NAME)
    dock.setFeatures(features)
    return dock


def _subclass(name, base=QWidget):
    return type(name, (base,), {})()


_WIDGET_CASES = {
    "push": (lambda: QPushButton(NAME), RUN),
    "push_mnemonic": (lambda: QPushButton("&Zorbix…"), RUN),
    "push_checkable": (_checkable_button, TOGGLE),
    "radio": (lambda: QRadioButton(NAME), SELECT),
    "radio_checkable_still_select": (lambda: QRadioButton(NAME), SELECT),
    "push_described": (_described_button, "Custom description."),
    "push_icon_only": (QPushButton, "Activate this control."),
    "push_accessible_name": (lambda: _named(QPushButton()), RUN),
    "tool_plain": (lambda: QToolButton(), "Activate this control."),
    "spin": (_spin, "Zorbix: enter or adjust a value from -5 px to 9 px."),
    "double_spin": (_double_spin, "Zorbix: enter or adjust a value from 0.5 to 2.5."),
    "slider": (_slider, "Zorbix: enter or adjust a value from 0 to 99."),
    "unnamed_spin": (QSpinBox, "Value: enter or adjust a value from 0 to 99."),
    "date_edit": (lambda: _named(QDateEdit()), EDIT),
    "combo": (lambda: _combo(False), "Choose an option for “Zorbix”."),
    "combo_editable": (lambda: _combo(True), "Choose an option or type a value for “Zorbix”."),
    "line": (lambda: _named(QLineEdit()), EDIT),
    "line_unnamed": (QLineEdit, "Edit “Value”."),
    "text": (lambda: _named(QTextEdit()), EDIT),
    "plain_text": (lambda: _named(QPlainTextEdit()), EDIT),
    "key_sequence": (lambda: _named(QKeySequenceEdit()), KEYS),
    "key_capture": (lambda: _named(_subclass("_KeyCaptureEdit", QLineEdit)), KEYS),
    "key_capture_unnamed": (lambda: _subclass("_KeyCaptureEdit", QLineEdit),
                            "Value: press the desired key combination to set this shortcut."),
    "label": (lambda: QLabel("R&D <notes"), "R&D <notes"),
    "label_rich": (lambda: QLabel("<b>Bold</b> text"), "Bold text"),
    "dock_movable": (lambda: _dock(QDockWidget.DockWidgetFeature.DockWidgetMovable),
                     "Zorbix: drag the title bar to reposition this panel."),
    "dock_fixed": (lambda: _dock(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures), NAME),
    "list": (QListWidget, "Select an item to work with it. Hover over a row to read its details."),
    "table": (lambda: QTableWidget(1, 1),
              "Select an item to work with it. Hover over a row to read its details."),
    "scrollbar": (QScrollBar, "Scroll to reveal more content."),
    "progress": (QProgressBar, "Show the progress of the current operation."),
    "canvas_by_class_name": (lambda: _subclass("GPUImageView"),
                             "Browse images here. Right-click for image actions and viewing "
                             "options."),
    "canvas_button_name_wins": (lambda: _subclass("_StarLabel", QPushButton),
                                "Click a star to set the image rating."),
    "plain_widget": (QWidget, ""),
    "frame": (QFrame, ""),
}


@pytest.mark.parametrize("case", sorted(_WIDGET_CASES))
def test_widget_help_text_for_each_control_kind(qapp, owned, case):
    factory, expected = _WIDGET_CASES[case]
    widget = factory()
    owned.append(widget)
    assert control_tooltips._widget_tip(widget) == expected


@pytest.mark.parametrize(("parent_type", "expected"), [
    (QLineEdit, "Clear this field."),
    (QTabBar, "Show more tabs when they do not all fit."),
    (QWidget, "Activate this control."),
])
def test_textless_child_buttons_follow_their_parent(qapp, owned, parent_type, expected):
    button, parent = _child_button(parent_type)
    owned.append(parent)
    assert control_tooltips._widget_tip(button) == expected


def test_text_on_a_line_edit_child_button_uses_the_normal_rules(qapp, owned):
    line = QLineEdit()
    owned.append(line)
    button = QToolButton(line)
    button.setText(NAME)
    assert control_tooltips._widget_tip(button) == RUN


def test_tool_button_with_default_action(qapp, owned):
    button = QToolButton()
    action = QAction(NAME, button)
    owned.append(button)
    button.setDefaultAction(action)
    assert control_tooltips._widget_tip(button) == RUN
    action.setToolTip("Authored help.")
    assert control_tooltips._widget_tip(button) == "Authored help"
    action.setToolTip(f"&{NAME}")
    assert control_tooltips._widget_tip(button) == RUN
    action.setToolTip("")
    action.setCheckable(True)
    action.setShortcut(QKeySequence("Ctrl+K"))
    assert control_tooltips._widget_tip(button) == f"{TOGGLE}\nShortcut: Ctrl+K"


def test_tool_button_whose_default_action_has_no_text_falls_back(qapp, owned):
    button = QToolButton()
    owned.append(button)
    button.setDefaultAction(QAction("", button))
    assert control_tooltips._widget_tip(button) == "Activate this control."


def test_splitter_handle_is_described_as_a_resize_control(qapp, owned):
    splitter = QSplitter()
    owned.append(splitter)
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    assert control_tooltips._widget_tip(splitter.handle(1)) == "Drag to resize the adjacent panels."


def test_internal_line_edit_uses_the_owner_help(qapp, owned):
    spin = _spin()
    owned.append(spin)
    editor = spin.findChild(QLineEdit)
    assert control_tooltips._widget_tip(editor) == (
        "Zorbix: enter or adjust a value from -5 px to 9 px.")
    spin.setToolTip("<qt>Owner &amp; help.</qt>")
    # The owner's help is reduced to a plain label, so a lone "&" reads as a mnemonic.
    assert control_tooltips._widget_tip(editor) == "Owner  help"
    combo = _combo(True)
    owned.append(combo)
    assert control_tooltips._widget_tip(combo.lineEdit()) == (
        "Choose an option or type a value for “Zorbix”.")
    keys = _named(QKeySequenceEdit())
    owned.append(keys)
    assert control_tooltips._widget_tip(keys.findChild(QLineEdit)) == KEYS


def _action(text=NAME, *, checkable=False, parent=None):
    action = QAction(text, parent)
    action.setCheckable(checkable)
    return action


def test_action_help_for_each_kind(qapp, owned):
    root = QWidget()
    owned.append(root)
    assert action_tip(_action(parent=root)) == RUN
    assert action_tip(_action("&Zorbix…", parent=root)) == RUN
    assert action_tip(_action(checkable=True, parent=root)) == TOGGLE
    exclusive, loose = QActionGroup(root), QActionGroup(root)
    loose.setExclusive(False)
    choice, extra = _action(checkable=True, parent=root), _action(checkable=True, parent=root)
    exclusive.addAction(choice)
    loose.addAction(extra)
    assert action_tip(choice) == SELECT
    assert action_tip(extra) == TOGGLE
    menu = QMenu(NAME, root)
    assert action_tip(menu.menuAction()) == "Open the “Zorbix” commands."
    assert action_tip(_action("", parent=root)) == ""
    separator = _action(parent=root)
    separator.setSeparator(True)
    assert action_tip(separator) == ""


def test_action_status_tip_and_shortcuts(qapp, owned):
    root = QWidget()
    owned.append(root)
    action = _action(parent=root)
    action.setStatusTip("Does the thing.")
    assert action_tip(action) == "Does the thing."
    action.setShortcuts([QKeySequence("Ctrl+A"), QKeySequence(), QKeySequence("Ctrl+B")])
    assert action_tip(action) == "Does the thing.\nShortcut: Ctrl+A, Ctrl+B"


def test_action_help_on_a_deleted_action_is_empty(qapp):
    action = _action()
    shiboken6.delete(action)
    assert action_tip(action) == ""


def test_stored_help_is_escaped_rich_text_and_tracks_changes(qapp, owned):
    action = _action("<a&&b>")
    owned.append(action)
    action.setShortcut(QKeySequence("Ctrl+J"))
    ensure_tooltip(action)
    expected = "<qt>Run “&lt;a&amp;b&gt;”.<br>Shortcut: Ctrl+J</qt>"
    assert action.toolTip() == expected
    assert action.property("imervueGeneratedToolTip") == expected
    action.setShortcut(QKeySequence())
    ensure_tooltip(action)
    assert action.toolTip() == "<qt>Run “&lt;a&amp;b&gt;”.</qt>"


def test_action_tooltip_equal_to_its_label_is_regenerated(qapp, owned):
    action = _action()
    owned.append(action)
    action.setToolTip("&Zorbix.")
    ensure_tooltip(action)
    assert action.toolTip() == f"<qt>{RUN}</qt>"
    action.setToolTip("Authored")
    ensure_tooltip(action)
    assert action.toolTip() == "Authored"


def test_widget_tooltip_equal_to_its_label_is_kept(qapp, owned):
    button = QPushButton(NAME)
    owned.append(button)
    button.setToolTip(NAME)
    ensure_tooltip(button)
    assert button.toolTip() == NAME


def test_empty_help_leaves_nothing_behind(qapp, owned):
    widget, action = QWidget(), _action("")
    owned.extend([widget, action])
    ensure_tooltip(widget)
    ensure_tooltip(action)
    assert widget.toolTip() == "" and widget.property("imervueGeneratedToolTip") is None
    assert action.property("imervueGeneratedToolTip") is None


def test_objects_without_tooltips_are_rejected(qapp, owned):
    obj = QObject()
    owned.append(obj)
    with pytest.raises(AttributeError):
        ensure_tooltip(obj)
    assert obj.property("imervueGeneratedToolTip") is None


def test_tab_help_generation_and_bookkeeping(qapp, owned):
    tabs = QTabBar()
    owned.append(tabs)
    tabs.addTab("&First")
    tabs.addTab("Second")
    tabs.setTabToolTip(1, "Authored tab")
    fill_missing_tooltips(tabs)
    assert tabs.tabToolTip(0) == "Switch to “First”."
    assert tabs.tabToolTip(1) == "Authored tab"
    assert tabs.property("imervueGeneratedTabTips") == ["Switch to “First”."]
    tabs.setTabText(1, "Third")
    tabs.setTabToolTip(1, "")
    fill_missing_tooltips(tabs)
    assert tabs.property("imervueGeneratedTabTips") == [
        "Switch to “First”.", "Switch to “Third”."]


def test_menu_walk_shows_tips_and_fills_its_actions(qapp, owned):
    menu = QMenu("Menu")
    owned.append(menu)
    action = menu.addAction(NAME)
    menu.addSeparator()
    fill_missing_tooltips(menu)
    assert menu.toolTipsVisible()
    assert action.toolTip() == f"<qt>{RUN}</qt>"


def _filter():
    return control_tooltips._ToolTipFilter()


def test_filter_ignores_other_events_and_non_widgets(qapp, owned):
    handler, button, obj = _filter(), QPushButton(NAME), QObject()
    owned.extend([handler, button, obj])
    assert handler.eventFilter(button, QEvent(QEvent.Type.Resize)) is False
    assert button.toolTip() == ""
    assert handler.eventFilter(obj, QEvent(QEvent.Type.Show)) is False
    assert handler.eventFilter(obj, QEvent(QEvent.Type.ToolTip)) is False


def test_filter_show_on_a_plain_widget_fills_only_that_widget(qapp, owned):
    handler, root = _filter(), QWidget()
    owned.extend([handler, root])
    QVBoxLayout(root).addWidget(QPushButton("Inner"))
    root.setAccessibleName(NAME)
    button = QPushButton(NAME)
    owned.append(button)
    assert handler.eventFilter(button, QShowEvent()) is False
    assert button.toolTip() == f"<qt>{RUN}</qt>"
    assert handler.eventFilter(root, QShowEvent()) is False
    assert root.findChild(QPushButton).toolTip() == ""


@pytest.mark.parametrize("window_type", [QMainWindow, QDialog])
def test_filter_show_on_a_window_fills_its_children(qapp, owned, window_type):
    handler, window = _filter(), window_type()
    owned.extend([handler, window])
    button = QPushButton(NAME, window)
    assert handler.eventFilter(window, QShowEvent()) is False
    assert button.toolTip() == f"<qt>{RUN}</qt>"


def test_filter_tooltip_event_on_a_window_does_not_walk_children(qapp, owned):
    handler, window = _filter(), QDialog()
    owned.extend([handler, window])
    button = QPushButton(NAME, window)
    assert handler.eventFilter(window, QEvent(QEvent.Type.ToolTip)) is False
    assert button.toolTip() == ""


def test_filter_skips_widgets_inside_tooltip_windows(qapp, owned):
    handler, popup = _filter(), QWidget(None, Qt.WindowType.ToolTip)
    owned.extend([handler, popup])
    button = QPushButton(NAME, popup)
    assert handler.eventFilter(button, QShowEvent()) is False
    assert button.toolTip() == ""


def _help_event(viewport, point=None):
    point = QPoint(8, 8) if point is None else point
    return QHelpEvent(QEvent.Type.ToolTip, point, viewport.mapToGlobal(point))


@pytest.fixture
def shown_tip(monkeypatch):
    show = MagicMock()
    monkeypatch.setattr(QToolTip, "showText", show)
    return show


def _shown_list(qapp, owned, *texts):
    view = QListWidget()
    owned.append(view)
    view.addItems(list(texts))
    view.show()
    qapp.processEvents()
    return view


def _item_point(view, row):
    return view.visualItemRect(view.item(row)).center()


def test_filter_item_tip_answers(qapp, owned, shown_tip):
    view = _shown_list(qapp, owned, "A < B", "", "Has tip")
    view.item(2).setToolTip("Own tip")
    handler = _filter()
    owned.append(handler)
    viewport = view.viewport()
    event = _help_event(viewport, _item_point(view, 0))
    assert handler.eventFilter(viewport, event) is True
    shown_tip.assert_called_once_with(event.globalPos(), "<qt>A &lt; B</qt>", viewport)
    for row in (1, 2):
        assert handler.eventFilter(viewport, _help_event(viewport, _item_point(view, row))) is False
    assert handler.eventFilter(viewport, _help_event(viewport, QPoint(5, 900))) is False
    assert shown_tip.call_count == 1
    assert viewport.toolTip() == ""


def test_filter_item_tip_is_skipped_when_the_viewport_has_help(qapp, owned, shown_tip):
    view = _shown_list(qapp, owned, "Row")
    handler = _filter()
    owned.append(handler)
    view.viewport().setToolTip("Viewport help")
    event = _help_event(view.viewport(), _item_point(view, 0))
    assert handler.eventFilter(view.viewport(), event) is False
    shown_tip.assert_not_called()
    assert handler.eventFilter(view, _help_event(view.viewport())) is False
    shown_tip.assert_not_called()


def _header(qapp, owned, *, tooltip=None, label="Column"):
    model = QStandardItemModel(1, 1)
    item = QStandardItem(label)
    if tooltip:
        item.setToolTip(tooltip)
    model.setHorizontalHeaderItem(0, item)
    view = QTableView()
    owned.extend([view, model])
    view.setModel(model)
    view.show()
    qapp.processEvents()
    return view.horizontalHeader()


@pytest.mark.parametrize(("tooltip", "label", "shown"), [
    (None, "Column <1>", "<qt>Column &lt;1&gt;</qt>"),
    ("Native help", "Column", None),
    (None, "", None),
])
def test_filter_header_tip_answers(qapp, owned, shown_tip, tooltip, label, shown):
    header = _header(qapp, owned, tooltip=tooltip, label=label)
    handler = _filter()
    owned.append(handler)
    result = handler.eventFilter(header.viewport(), _help_event(header.viewport()))
    assert result is (shown is not None)
    if shown is None:
        shown_tip.assert_not_called()
    else:
        assert shown_tip.call_args.args[1] == shown


def test_filter_header_outside_any_section(qapp, owned, shown_tip):
    header = _header(qapp, owned)
    handler = _filter()
    owned.append(handler)
    point = QPoint(header.length() + 50, 4)
    assert handler.eventFilter(header.viewport(), _help_event(header.viewport(), point)) is False
    shown_tip.assert_not_called()


def test_install_tooltips_without_an_application_is_a_no_op():
    control_tooltips.install_tooltips(None)
