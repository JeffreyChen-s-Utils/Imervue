"""Top-level Paint workspace widget.

A QMainWindow used as the centralWidget of a QTabWidget page. Embedding
a QMainWindow inside another QMainWindow is unusual but well-supported
by Qt and is the simplest way to host real QDockWidgets — the alternative
(plain QSplitter layout) loses floating / re-docking / collapse-arrow
behaviour that users expect from MediBang and PS-style apps.

Layout:

* Top: PaintOptionsBar — context-sensitive options strip.
* Left: PaintToolBar — vertical icon bar (added as a regular toolbar).
* Centre: PaintCanvas — the GL drawing surface.
* Right: ColorDock + BrushDock + LayerDock + NavigatorDock + HistoryDock,
  stacked top-to-bottom in dock area :data:`Qt.RightDockWidgetArea`.

Phase 1 wires every signal back to the shared ToolState singleton so
state changes propagate everywhere, but tool dispatch on the canvas is
not yet a paint operation — Phase 2 plugs the brush engine into
:meth:`PaintCanvas.set_tool_dispatcher`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QMenuBar, QStatusBar

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas, cursor_for_tool
from Imervue.paint.dock_panels import (
    BrushDock,
    ColorDock,
    HistoryDock,
    LayerDock,
    NavigatorDock,
)
from Imervue.paint.tool_bar import PaintOptionsBar, PaintToolBar
from Imervue.paint.tool_dispatcher import ToolDispatcher

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

logger = logging.getLogger("Imervue.paint.workspace")


class PaintWorkspace(QMainWindow):
    """Assembles the Paint tab from the toolbar + canvas + dock pieces."""

    def __init__(self, state: ToolState | None = None, parent=None):
        super().__init__(parent)
        self._state = state if state is not None else ts.load_tool_state()

        # The embedded main window must not show its own menu bar — the host
        # main window already owns one.
        empty_menu = QMenuBar(self)
        empty_menu.hide()
        self.setMenuBar(empty_menu)

        # Status bar shows the cursor's image-space coordinates while painting.
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)

        # Central canvas
        self._canvas = PaintCanvas(self)
        self.setCentralWidget(self._canvas)

        # Top tool-options strip
        self._options_bar = PaintOptionsBar(self._state, self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._options_bar)

        # Left icon bar
        self._tool_bar = PaintToolBar(self._state, self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._tool_bar)

        # Right dock column — order matches MediBang's defaults
        self._color_dock = ColorDock(self._state, self)
        self._brush_dock = BrushDock(self._state, self)
        self._layer_dock = LayerDock(self)
        self._navigator_dock = NavigatorDock(self)
        self._history_dock = HistoryDock(self)

        for dock in (
            self._color_dock,
            self._brush_dock,
            self._layer_dock,
            self._navigator_dock,
            self._history_dock,
        ):
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            dock.setFeatures(
                dock.features()
                | dock.DockWidgetFeature.DockWidgetMovable
                | dock.DockWidgetFeature.DockWidgetFloatable,
            )

        # Wire status-bar hover updates and tool-driven cursor changes.
        self._canvas.hover_changed.connect(self._on_hover_changed)
        self._canvas.image_loaded.connect(self._on_image_loaded)
        self._navigator_dock.zoom_changed.connect(self._on_navigator_zoom)
        self._navigator_dock.fit_requested.connect(self._canvas.reset_view)

        # Tool dispatcher routes pointer events to the active tool. The
        # canvas owns the live image, so we hand the dispatcher a getter
        # rather than caching a snapshot.
        self._dispatcher = ToolDispatcher(self._state, self._canvas.current_image)
        self._canvas.set_tool_dispatcher(self._dispatcher)

        self._unsubscribe = self._state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._refresh_cursor_for_tool()

    # ---- public ----------------------------------------------------------

    def canvas(self) -> PaintCanvas:
        return self._canvas

    def state(self) -> ToolState:
        return self._state

    def load_image(self, arr) -> None:
        """Forward an HxWx4 RGBA buffer to the central canvas."""
        self._canvas.load_image(arr)

    # ---- handlers --------------------------------------------------------

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_TOOL:
            self._refresh_cursor_for_tool()

    def _refresh_cursor_for_tool(self) -> None:
        self._canvas.set_cursor_for_tool(self._state.tool)

    def _on_hover_changed(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            self._status.clearMessage()
            return
        msg = language_wrapper.language_word_dict.get(
            "paint_status_cursor", "x: {x}  y: {y}",
        ).format(x=x, y=y)
        self._status.showMessage(msg)

    def _on_image_loaded(self, w: int, h: int) -> None:
        msg = language_wrapper.language_word_dict.get(
            "paint_status_image_loaded", "Canvas: {w} × {h}",
        ).format(w=w, h=h)
        self._status.showMessage(msg, 3000)

    def _on_navigator_zoom(self, factor: float) -> None:  # pragma: no cover - GL
        # Phase 2 will wire this to the canvas' zoom setter directly.
        # For Phase 1 the slider just records the user's intent.
        logger.debug("navigator zoom set to %.2fx", factor)

    # ---- compatibility shim ---------------------------------------------

    @staticmethod
    def cursor_for_tool(tool: str) -> Qt.CursorShape:
        """Re-exported for callers that don't want to import canvas."""
        return cursor_for_tool(tool)
