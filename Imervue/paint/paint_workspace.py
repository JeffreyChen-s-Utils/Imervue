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

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMainWindow, QStatusBar

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas, cursor_for_tool
from Imervue.paint.dock_panels import (
    BrushDock,
    ColorDock,
    HistoryDock,
    LayerDock,
    MaterialDock,
    NavigatorDock,
)
from Imervue.paint.file_menu import populate_file_menu
from Imervue.paint.paint_menu_bar import build_paint_menu_bar
from Imervue.paint.tool_bar import PaintOptionsBar, PaintToolBar
from Imervue.paint.tool_dispatcher import ToolDispatcher

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class PaintWorkspace(QMainWindow):
    """Assembles the Paint tab from the toolbar + canvas + dock pieces."""

    def __init__(self, state: ToolState | None = None, parent=None):
        super().__init__(parent)
        self._state = state if state is not None else ts.load_tool_state()

        # The embedded main window has its own menu bar so File / Edit
        # / Layer / View / Tools / Filter / Settings / Window all live
        # together — :func:`build_paint_menu_bar` populates the Filter
        # menu and stashes the others on the workspace as
        # ``_<key>_menu`` for the 21b–21g sub-phases to fill.
        self.setMenuBar(build_paint_menu_bar(self))
        populate_file_menu(self)

        # Status bar shows the cursor's image-space coordinates while painting.
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)

        # Central canvas. Seeded with a default white canvas so the user
        # can start painting the moment the workspace opens — without a
        # layer the tool dispatcher's ``image_provider`` returns ``None``
        # and brush strokes silently no-op.
        self._canvas = PaintCanvas(self)
        self._canvas.new_blank_document()
        self.setCentralWidget(self._canvas)

        # Top tool-options strip
        self._options_bar = PaintOptionsBar(self._state, self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._options_bar)

        # Left icon bar
        self._tool_bar = PaintToolBar(self._state, self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._tool_bar)

        # Right dock column — order matches MediBang's defaults. The
        # layer dock is bound to the canvas's PaintDocument so external
        # changes (tool that adds a layer, file load) refresh the panel.
        self._color_dock = ColorDock(self._state, self)
        self._brush_dock = BrushDock(self._state, self)
        self._layer_dock = LayerDock(self._canvas.document(), self)
        self._navigator_dock = NavigatorDock(self)
        self._history_dock = HistoryDock(self)
        self._material_dock = MaterialDock(parent=self)

        for dock in (
            self._color_dock,
            self._brush_dock,
            self._layer_dock,
            self._navigator_dock,
            self._material_dock,
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
        self._navigator_dock.zoom_changed.connect(self._canvas.set_zoom)
        self._navigator_dock.fit_requested.connect(self._canvas.reset_view)
        self._canvas.zoom_changed.connect(self._navigator_dock.set_zoom)

        # MaterialDock thumbnail clicks → drop the chosen tile onto a
        # fresh layer. Categories beyond ``pose`` (texture / pattern /
        # tone / brush_tip) will route to their own consumers in later
        # phases; pose is the first wired through.
        self._material_dock.material_chosen.connect(self._on_material_chosen)

        # Throttled navigator-preview updates. ``document_changed`` fires
        # on every brush dab; rebuilding the QPixmap each time would
        # double the per-stroke cost. Coalesce into a single update
        # ~6 fps via a singleshot timer started on the first dirty event
        # and refreshed only after it fires.
        self._nav_dirty = False
        self._nav_timer = QTimer(self)
        self._nav_timer.setSingleShot(True)
        self._nav_timer.setInterval(160)
        self._nav_timer.timeout.connect(self._refresh_navigator_preview)
        self._canvas.document_changed.connect(self._on_document_changed)
        # Push the seeded blank canvas into the navigator immediately so
        # the user sees something on first open.
        self._refresh_navigator_preview()
        # Sync the slider with the canvas's actual zoom (which may have
        # been auto-fitted between the seed and now).
        self._navigator_dock.set_zoom(self._canvas.zoom_factor())

        # Tool dispatcher routes pointer events to the active tool. The
        # canvas owns the live image and selection mask, so we hand the
        # dispatcher getters rather than caching snapshots.
        self._dispatcher = ToolDispatcher(
            self._state,
            image_provider=self._canvas.current_image,
            selection_provider=self._canvas.current_selection,
            set_selection=self._canvas.set_selection,
            parent_widget=self,
        )
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
        """Forward an HxWx4 RGBA buffer to the central canvas.

        ``None`` resets to a fresh blank canvas — never to an empty
        document. The Paint workspace is always for painting, so the
        invariant "there is always a layer to paint on" must hold even
        when the host main window passes ``None`` to indicate "no
        source image is bound".
        """
        if arr is None:
            self._canvas.new_blank_document()
        else:
            self._canvas.load_image(arr)
        # The canvas swapped its PaintDocument; rebind the layer dock
        # so it re-subscribes and refreshes against the new stack.
        self._layer_dock.set_document(self._canvas.document())

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

    def _on_material_chosen(self, path: str) -> None:
        """Drop a material onto the canvas — currently routes pose
        category onto a new layer; other categories are placeholders."""
        from pathlib import Path

        from Imervue.paint.material_library import MaterialEntry
        from Imervue.paint.pose_drop import fit_pose_to_canvas, load_pose_image

        # Look up the entry's category in the dock's index. Falls back
        # to the file extension if the path isn't in the index (the
        # user dragged in a file from outside the configured root).
        entry = next(
            (e for e in self._material_dock.index().entries
             if str(e.path) == path),
            None,
        )
        if entry is None:
            entry = MaterialEntry(name=Path(path).stem, path=Path(path))
        if entry.category != "pose":
            # Other categories are wired in later phases.
            return
        canvas_doc = self._canvas.document()
        if canvas_doc.shape is None:
            return
        try:
            pose = load_pose_image(entry.path)
        except (OSError, ValueError):
            return
        fitted = fit_pose_to_canvas(pose, canvas_doc.shape)
        layer = canvas_doc.add_layer(name=f"Pose · {entry.name}")
        np.copyto(layer.image, fitted)
        canvas_doc.invalidate_composite()
        self._canvas.update()

    def _on_document_changed(self) -> None:
        """Mark the navigator preview dirty and start the coalesce timer."""
        self._nav_dirty = True
        if not self._nav_timer.isActive():
            self._nav_timer.start()

    def _refresh_navigator_preview(self) -> None:
        """Build a QPixmap of the current composite and push it to the dock."""
        self._nav_dirty = False
        composite = self._canvas.document().composite()
        if composite is None:
            self._navigator_dock.set_preview_image(None)
            return
        h, w = composite.shape[:2]
        # ``composite`` may alias ``layer.image`` via the single-layer
        # fast path. QImage with bytesPerLine on a numpy view is safe so
        # long as the buffer stays alive — keep a reference on self
        # until the next refresh.
        self._nav_buffer = composite.tobytes()
        qimage = QImage(
            self._nav_buffer, w, h, w * 4, QImage.Format.Format_RGBA8888,
        )
        self._navigator_dock.set_preview_image(QPixmap.fromImage(qimage))

    # ---- compatibility shim ---------------------------------------------

    @staticmethod
    def cursor_for_tool(tool: str) -> Qt.CursorShape:
        """Re-exported for callers that don't want to import canvas."""
        return cursor_for_tool(tool)
