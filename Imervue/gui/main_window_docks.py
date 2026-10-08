"""Dock panels of the main window's Imervue and Modify tabs.

Each of the two tabs is a nested ``QMainWindow`` (the pattern the Paint
workspace already uses), so its side panels are real docks: the user can
resize, move, tab, float and close them, and the centre widget always gets the
width that is left. Nothing here calls ``QSplitter.setSizes``, which holds
absolute pane widths and has to be recomputed by hand whenever the window, the
screen or the font size changes.

The pure helpers (:func:`encode_dock_state`, :func:`decode_dock_state`) are
module-level; :class:`MainWindowDocksMixin` holds the builders and the layout
commands ``ImervueMainWindow`` mixes in.
"""
from __future__ import annotations

from base64 import b64decode, b64encode

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QStackedWidget, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict

BROWSE_DOCK_STATE_KEY = "browse_dock_state"
MODIFY_DOCK_STATE_KEY = "modify_dock_state"

# Stable ids for ``QMainWindow.saveState`` / ``restoreState``: the window title
# is translated, so Qt needs a name that does not change with the language.
TREE_DOCK_NAME = "browse_dock_folders"
INFO_DOCK_NAME = "browse_dock_info"
ISSUE_DOCK_NAME = "browse_dock_image_issues"
TOOLS_DOCK_NAME = "modify_dock_tools"
PROPERTIES_DOCK_NAME = "modify_dock_properties"


def encode_dock_state(blob: bytes) -> str:
    """Base64 text of a ``saveState`` blob, for the JSON settings file."""
    return b64encode(bytes(blob)).decode("ascii")


def decode_dock_state(encoded: object) -> bytes:
    """The ``saveState`` blob behind *encoded*; empty when it is missing or not base64."""
    if not isinstance(encoded, str) or not encoded:
        return b""
    try:
        return b64decode(encoded, validate=True)
    except ValueError:   # binascii.Error, which b64decode raises, is one
        return b""


def make_dock_host() -> QMainWindow:
    """A ``QMainWindow`` that lives inside a tab page and only lays out docks."""
    host = QMainWindow()
    host.setWindowFlags(Qt.WindowType.Widget)
    host.setDockNestingEnabled(True)
    return host


def add_dock(host: QMainWindow, name: str, title: str, widget: QWidget,
             area: Qt.DockWidgetArea) -> QDockWidget:
    """Dock *widget* into *area* of *host* under the stable object name *name*."""
    dock = QDockWidget(title, host)
    dock.setObjectName(name)
    dock.setWidget(widget)
    host.addDockWidget(area, dock)
    return dock


class CanvasHost(QStackedWidget):
    """Centre of the Modify tab: a hint until an image is bound, then its canvas.

    Being the central widget of a dock host, it is handed whatever width the
    tool and adjustment docks leave, on every resize and screen change.
    """

    def __init__(self, hint: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._hint = QLabel(hint)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.setEnabled(False)
        self.addWidget(self._hint)

    def set_canvas(self, canvas: QWidget) -> None:
        """Show *canvas* in place of the hint (or of the canvas shown before)."""
        self.addWidget(canvas)
        self.setCurrentWidget(canvas)

    def shows_hint(self) -> bool:
        """Whether no canvas is shown."""
        return self.currentWidget() is self._hint


class MainWindowDocksMixin:
    """Builds, saves, restores and resets the docks of the Imervue and Modify tabs."""

    def _build_browse_docks(self) -> None:
        """Folders on the left of the viewer; image info and load issues on its right."""
        lang = language_wrapper.language_word_dict
        host = self._browse_window
        self._tree_dock = add_dock(
            host, TREE_DOCK_NAME, lang.get("dock_folders", "Folders"),
            self._tree_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._info_dock = add_dock(
            host, INFO_DOCK_NAME, lang.get("dock_image_info", "Image Info"),
            self.exif_sidebar, Qt.DockWidgetArea.RightDockWidgetArea)
        # Reading EXIF costs a file read per image, so the panel only does it while shown.
        self._info_dock.visibilityChanged.connect(self.exif_sidebar.set_active)
        self._image_issue_dock = add_dock(
            host, ISSUE_DOCK_NAME, lang.get("image_issues_title", "Image load issues"),
            self.image_issue_panel, Qt.DockWidgetArea.RightDockWidgetArea)
        self._image_issue_dock.hide()

    def _build_modify_docks(self, tools: QWidget, properties: QWidget) -> None:
        """Annotation tools on the left of the canvas, adjustments on its right."""
        lang = language_wrapper.language_word_dict
        host = self._modify_window
        self._modify_tools_dock = add_dock(
            host, TOOLS_DOCK_NAME, lang.get("dock_modify_tools", "Tools"),
            tools, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._modify_properties_dock = add_dock(
            host, PROPERTIES_DOCK_NAME, lang.get("dock_modify_adjustments", "Adjustments"),
            properties, Qt.DockWidgetArea.RightDockWidgetArea)

    def panel_docks(self) -> list[tuple[str, list[QDockWidget]]]:
        """The docks grouped under the title of the tab they belong to, in menu order."""
        tabs = self._main_tabs
        return [
            (tabs.tabText(tabs.indexOf(self._browse_window)),
             [self._tree_dock, self._info_dock, self._image_issue_dock]),
            (tabs.tabText(tabs.indexOf(self._modify_window)),
             [self._modify_tools_dock, self._modify_properties_dock]),
        ]

    def _dock_hosts(self) -> tuple[tuple[str, QMainWindow], ...]:
        return ((BROWSE_DOCK_STATE_KEY, self._browse_window),
                (MODIFY_DOCK_STATE_KEY, self._modify_window))

    def dock_layout_states(self) -> dict[str, str]:
        """Both tabs' dock layouts as base64 text, keyed by their settings key."""
        return {key: encode_dock_state(host.saveState().data())
                for key, host in self._dock_hosts()}

    def apply_dock_layout_states(self, states: dict) -> None:
        """Apply the layouts in *states*; a missing or rejected one keeps what is shown."""
        for key, host in self._dock_hosts():
            blob = decode_dock_state(states.get(key))
            if blob:
                host.restoreState(QByteArray(blob))

    def browse_split_widths(self) -> list[int]:
        """Widths of the folder dock and the viewer column beside it."""
        return [self._tree_dock.width(), self._browse_window.centralWidget().width()]

    def _save_dock_layouts(self) -> None:
        """Store both tabs' dock layouts in ``user_setting_dict``."""
        user_setting_dict.update(self.dock_layout_states())

    def _restore_dock_layouts(self) -> None:
        """Apply the dock layouts saved in ``user_setting_dict``."""
        self.apply_dock_layout_states(user_setting_dict)

    def reset_panel_layout(self) -> None:
        """Put every dock back where it starts and forget the saved layouts."""
        left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
        placements = (
            (self._browse_window, self._tree_dock, left, True),
            (self._browse_window, self._info_dock, right, True),
            (self._browse_window, self._image_issue_dock, right,
             self.image_issue_panel.issue_count() > 0),
            (self._modify_window, self._modify_tools_dock, left, True),
            (self._modify_window, self._modify_properties_dock, right, True),
        )
        for host, dock, area, visible in placements:
            dock.setFloating(False)
            host.addDockWidget(area, dock)
            dock.setVisible(visible)
        for key, _host in self._dock_hosts():
            user_setting_dict.pop(key, None)

    def set_tree_dock_width(self, width: int) -> None:
        """Give the folder dock *width* pixels (a workspace saved before the docks did)."""
        if width > 0:
            self._browse_window.resizeDocks(
                [self._tree_dock], [int(width)], Qt.Orientation.Horizontal)
