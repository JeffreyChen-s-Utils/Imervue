"""Puppet workspace onboarding and compact, scrollable inspector layout."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabBar, QVBoxLayout

from Imervue.gui.panel_scroll import scroll_dock_content
from Imervue.gui.workspace_widgets import WorkspaceWelcome
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.ui_scale import scaled_px


def build_welcome(workspace):
    lang = language_wrapper.language_word_dict
    canvas = workspace.canvas()
    card = WorkspaceWelcome(
        lang.get("puppet_welcome_title", "Bring a character to life"),
        lang.get("puppet_welcome_hint", "Open a puppet rig or import artwork to start animating."),
        canvas,
    )
    card.setMaximumWidth(scaled_px(420))
    card.add_action(workspace._open_action.text(), workspace._open_action.trigger, primary=True)
    card.add_action(workspace._import_png_action.text(), workspace._import_png_action.trigger)
    examples = card.add_action(lang.get("puppet_examples", "Examples"), lambda: None)
    examples.setMenu(workspace._examples_menu)
    layout = QVBoxLayout(canvas)
    layout.setContentsMargins(*(scaled_px(16),) * 4)
    layout.addStretch()
    layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
    layout.addStretch()
    def document_loaded():
        loaded = canvas.document() is not None
        was_empty = not card.isHidden()
        card.setVisible(not loaded)
        if not loaded:
            workspace._motion_dock.hide()
        elif was_empty:
            workspace._motion_dock.show()
            size_inspectors(workspace)

    canvas.document_loaded.connect(document_loaded)
    workspace._motion_dock.hide()
    return card


def configure_inspectors(workspace):
    docks = (workspace._parameter_dock, workspace._expression_dock,
             workspace._pose_dock, workspace._bone_tree_dock, workspace._motion_dock)
    names = ("parameters", "expressions", "pose", "bones", "motions")
    for name, dock in zip(names, docks, strict=True):
        dock.setObjectName(f"puppet_dock_{name}")
        if dock is not workspace._motion_dock:
            scroll_dock_content(dock)
    workspace._parameter_dock.raise_()
    for tabs in workspace.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly):
        tabs.setExpanding(False)
        tabs.setUsesScrollButtons(True)
        tabs.setElideMode(Qt.TextElideMode.ElideRight)
        for index in range(tabs.count()):
            tabs.setTabToolTip(index, tabs.tabText(index))


def size_inspectors(workspace):
    workspace.resizeDocks([workspace._parameter_dock], [scaled_px(300)], Qt.Orientation.Horizontal)
    workspace.resizeDocks([workspace._motion_dock], [scaled_px(190)], Qt.Orientation.Vertical)
