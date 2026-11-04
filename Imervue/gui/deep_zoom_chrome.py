"""Deep Zoom gives the image the room: side panels and the filter row fold into icon buttons.

Entering Deep Zoom hides the docked Folders and Image Info panels and the filter
row above the viewer. Small checkable icon buttons beside the file name bring
each one back for as long as Deep Zoom stays open; leaving Deep Zoom puts every
panel back the way it was before. A floating dock takes no room from the image,
so it is left alone.

:class:`CollapseState` is the pure bookkeeping; :class:`DeepZoomChrome` is the
Qt shell the main window builds once its docks exist.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager

from PySide6.QtCore import QObject, QSize, QTimer
from PySide6.QtWidgets import QDockWidget, QToolButton, QWidget

from Imervue.gui.tool_icons import tool_icon
from Imervue.system.ui_scale import scaled_px

PANEL_FOLDERS = "folders"
PANEL_FILTERS = "filters"
PANEL_INFO = "info"

# Glyph in ``tool_icons`` drawn on each panel's button.
PANEL_ICONS = {PANEL_FOLDERS: "folder", PANEL_FILTERS: "filter", PANEL_INFO: "info"}


class CollapseState:
    """Which panels were shown before Deep Zoom folded them away."""

    def __init__(self) -> None:
        self._shown_before: dict[str, bool] | None = None

    @property
    def collapsed(self) -> bool:
        """Whether the panels are folded away right now."""
        return self._shown_before is not None

    def collapse(self, shown: Mapping[str, bool]) -> dict[str, bool]:
        """Remember *shown*; the visibility to apply is every panel hidden.

        Already collapsed, nothing changes: the panels the user brought back
        while Deep Zoom stayed open (another image of the folder) stay out.
        """
        if self._shown_before is not None:
            return {}
        self._shown_before = dict(shown)
        return dict.fromkeys(shown, False)

    def expand(self) -> dict[str, bool]:
        """Forget the snapshot and return it: the visibility to put back."""
        shown, self._shown_before = self._shown_before or {}, None
        return shown

    def remembered(self) -> dict[str, bool]:
        """The visibility from before the collapse; empty when not collapsed."""
        return dict(self._shown_before or {})

    def forget(self) -> None:
        """Drop the snapshot without restoring it (a new layout replaced it)."""
        self._shown_before = None


def _collapsible(panel: QWidget) -> bool:
    """A floating dock takes no room from the image, so Deep Zoom leaves it alone."""
    return not (isinstance(panel, QDockWidget) and panel.isFloating())


def _show(panel: QWidget, visible: bool) -> None:
    panel.setVisible(visible)
    if visible and isinstance(panel, QDockWidget):
        panel.raise_()   # the front tab when it shares its area with another dock


class DeepZoomChrome(QObject):
    """Folds *panels* away in Deep Zoom and offers a toggle button for each.

    *wanted* answers whether the panels should be folded now: ``True`` in Deep
    Zoom, ``False`` outside it, ``None`` to leave them as they are (theater mode
    owns every panel's visibility while it is on).
    """

    def __init__(self, panels: Mapping[str, QWidget], tips: Mapping[str, str],
                 wanted: Callable[[], bool | None], parent: QObject | None = None):
        super().__init__(parent)
        self._panels = dict(panels)
        self._wanted = wanted
        self._state = CollapseState()
        # Showing the next image clears Deep Zoom and loads it again in one go;
        # deciding once the event loop is back sees only where it ended up.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.sync)
        self.buttons = {name: self._make_button(name, tips.get(name, ""))
                        for name in self._panels}
        for panel in self._panels.values():
            if isinstance(panel, QDockWidget):
                panel.visibilityChanged.connect(self._refresh_buttons)

    @property
    def collapsed(self) -> bool:
        """Whether the panels are folded away right now."""
        return self._state.collapsed

    def _make_button(self, name: str, tip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName(f"deepZoomToggle_{name}")
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setIcon(tool_icon(PANEL_ICONS[name]))
        side = scaled_px(16)
        button.setIconSize(QSize(side, side))
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.hide()
        button.clicked.connect(lambda checked, n=name: self._toggle(n, checked))
        return button

    def schedule_sync(self) -> None:
        """Decide once control is back in the event loop (see :meth:`sync`)."""
        self._timer.start()

    def sync(self) -> None:
        """Fold or restore the panels to match :attr:`wanted`."""
        wanted = self._wanted()
        if wanted is None:
            return
        if wanted:
            self._collapse()
        else:
            self._expand()

    def relayout(self) -> None:
        """A dock layout was just applied: fold the panels it shows, and remember those."""
        if self._state.collapsed:
            self._state.forget()
            self._set_buttons_shown(False)
            self.sync()

    @contextmanager
    def uncollapsed(self) -> Iterator[None]:
        """Show the panels as they were before Deep Zoom while the block runs.

        A dock layout saved from inside the block (on close, into a workspace)
        is the user's layout, not one with every panel folded away.
        """
        if not self._state.collapsed:
            yield
            return
        current = self._visibility()
        self._apply(self._state.remembered())
        try:
            yield
        finally:
            self._apply(current)

    def _collapse(self) -> None:
        shown = {name: shown for name, shown in self._visibility().items()
                 if _collapsible(self._panels[name])}
        self._apply(self._state.collapse(shown))
        self._set_buttons_shown(True)

    def _expand(self) -> None:
        if not self._state.collapsed:
            return
        self._apply(self._state.expand())
        self._set_buttons_shown(False)

    def _toggle(self, name: str, checked: bool) -> None:
        _show(self._panels[name], checked)
        self._refresh_buttons()

    def _visibility(self) -> dict[str, bool]:
        return {name: not panel.isHidden() for name, panel in self._panels.items()}

    def _apply(self, visibility: Mapping[str, bool]) -> None:
        for name, visible in visibility.items():
            panel = self._panels.get(name)
            if panel is not None:
                _show(panel, visible)
        self._refresh_buttons()

    def _set_buttons_shown(self, shown: bool) -> None:
        for button in self.buttons.values():
            button.setVisible(shown)
        self._refresh_buttons()

    def _refresh_buttons(self, *_args) -> None:
        for name, button in self.buttons.items():
            button.setChecked(not self._panels[name].isHidden())
