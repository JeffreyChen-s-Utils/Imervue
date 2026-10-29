"""Canvas / tool-state signal handlers for the Paint workspace.

Split out of :mod:`paint_workspace` to keep the coordinator small.
:class:`CanvasEventsMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`; it owns the tool
cursor, the per-tool dock raise, the hover / image-loaded status updates
and the coalesced navigator + histogram preview.
"""
from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts


class CanvasEventsMixin:
    """Reacts to tool-state, hover, zoom and document-change signals.

    Expects the host to provide ``_state``, ``_canvas``, ``_status``,
    ``_navigator_dock``, ``_nav_timer``, the tool docks and the status /
    welcome-hint / secondary-view helpers of the sibling mixins.
    """

    # Tools whose cursor is the full-featured brush ring (diameter
    # tracks size × zoom).
    _BRUSH_RING_TOOLS = frozenset({
        "brush", "eraser", "smudge", "blur", "clone_stamp",
        "dodge", "burn", "sponge",
    })

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_TOOL:
            self._refresh_cursor_for_tool()
            self._raise_dock_for_tool()
            self._refresh_status_line()
        elif channel == ts.EVENT_BRUSH:
            # Brush size / kind change — refresh the size-preview ring
            # so the cursor reflects the new diameter immediately.
            if self._state.tool in self._BRUSH_RING_TOOLS:
                self._refresh_cursor_for_tool()
            self._refresh_status_line()

    def _refresh_cursor_for_tool(self) -> None:
        tool = self._state.tool
        if tool in self._BRUSH_RING_TOOLS:
            self._canvas.set_brush_size_cursor(
                self._state.brush.size,
                self._canvas.zoom_factor(),
                kind=tool,
            )
        else:
            self._canvas.set_cursor_for_tool(tool)

    def _on_zoom_changed_refresh_cursor(self, zoom: float) -> None:
        """Re-draw the brush ring at the new screen-pixel diameter when
        the active tool uses it, and sync the status-bar zoom chip."""
        if self._state.tool in self._BRUSH_RING_TOOLS:
            self._refresh_cursor_for_tool()
        self._refresh_zoom_indicator(zoom)

    def _raise_dock_for_tool(self) -> None:
        """Bring the dock holding the active tool's options to the
        front of its tab cluster on tool switch."""
        tool = self._state.tool
        targets = {
            "brush": self._brush_dock,
            "eraser": self._brush_dock,
            "fill": self._fill_dock,
            "eyedropper": self._color_dock,
            "text": self._brush_dock,   # text shares the brush cluster slot
        }
        dock = targets.get(tool)
        if dock is None:
            return
        # raise_() is a no-op for a non-tabbed (top-level) dock.
        dock.raise_()

    def _on_hover_changed(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            self._last_hover = None
        else:
            self._last_hover = (int(x), int(y))
        self._refresh_status_line()

    def _on_image_loaded(self, w: int, h: int) -> None:
        msg = language_wrapper.language_word_dict.get(
            "paint_status_image_loaded", "Canvas: {w} × {h}",
        ).format(w=w, h=h)
        self._status.showMessage(msg, 3000)
        # First image landed → the welcome hint has done its job.
        self._dismiss_welcome_hint()
        # Fresh content, no edits yet, so the tab is clean.
        self._set_tab_dirty(self._canvas, False)

    # ---- navigator preview ---------------------------------------------

    def _on_document_changed(self) -> None:
        """Mark the navigator preview dirty and start the coalesce timer.

        Also refreshes the status line so layer-level changes update the
        layer + selection segments without waiting for the next hover
        event, and tears down the welcome hint on the first real edit.
        """
        self._nav_dirty = True
        if not self._nav_timer.isActive():
            self._nav_timer.start()
        self._refresh_status_line()
        self._dismiss_welcome_hint()

    def _refresh_navigator_preview(self) -> None:
        """Build a QPixmap of the current composite and push it to the dock.

        Also refreshes the histogram dock from the same composite — both
        consumers piggyback on the same coalesce timer to avoid re-running
        per brush dab.
        """
        self._nav_dirty = False
        composite = self._canvas.document().composite()
        if composite is None:
            self._navigator_dock.set_preview_image(None)
            if hasattr(self, "_histogram_dock"):
                from Imervue.paint.histogram import empty_histogram
                self._histogram_dock.set_histogram(empty_histogram())
            return
        h, w = composite.shape[:2]
        # ``composite`` may alias ``layer.image`` via the single-layer
        # fast path. QImage on a numpy view is safe so long as the buffer
        # stays alive — keep a reference on self until the next refresh.
        self._nav_buffer = composite.tobytes()
        qimage = QImage(
            self._nav_buffer, w, h, w * 4, QImage.Format.Format_RGBA8888,
        )
        self._navigator_dock.set_preview_image(QPixmap.fromImage(qimage))
        if hasattr(self, "_histogram_dock"):
            from Imervue.paint.histogram import compute_histogram
            self._histogram_dock.set_histogram(compute_histogram(composite))
        # Push to any open secondary views so they stay in sync.
        self._push_composite_to_secondary_views(composite)
