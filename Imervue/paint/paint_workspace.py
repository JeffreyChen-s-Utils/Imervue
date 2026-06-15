"""Top-level Paint workspace widget.

A QMainWindow used as the centralWidget of a QTabWidget page. Embedding
a QMainWindow inside another QMainWindow is unusual but well-supported
by Qt and is the simplest way to host real QDockWidgets — the alternative
(plain QSplitter layout) loses floating / re-docking / collapse-arrow
behaviour that users expect from raster paint apps and PS-style apps.

Layout:

* Top: PaintOptionsBar — context-sensitive options strip.
* Left: PaintToolBar — vertical icon bar (added as a regular toolbar).
* Centre: PaintCanvas — the GL drawing surface.
* Right: ColorDock + BrushDock + LayerDock + NavigatorDock + HistoryDock,
  stacked top-to-bottom in dock area :data:`Qt.RightDockWidgetArea`.

The class is a thin coordinator: construction is delegated to
:class:`~Imervue.paint.workspace_docks.DockBuilder`, and the behaviour
clusters (autosave, tabs, docks, content ops, status line, shortcuts)
live in the focused mixins it composes. This module keeps the canvas /
dispatcher wiring, the drag-drop entry points, the cursor + state-event
plumbing and the navigator refresh.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas, cursor_for_tool
from Imervue.paint.edit_menu import populate_edit_menu
from Imervue.paint.file_menu import populate_file_menu
from Imervue.paint.image_menu import populate_image_menu
from Imervue.paint.layer_menu import populate_layer_menu
from Imervue.paint.manga_menu import populate_manga_menu
from Imervue.paint.paint_menu_bar import build_paint_menu_bar
from Imervue.paint.settings_menu import populate_settings_menu
from Imervue.paint.tool_bar import PaintOptionsBar, PaintToolBar
from Imervue.paint.tool_dispatcher import ToolDispatcher
from Imervue.paint.tools_menu import populate_tools_menu
from Imervue.paint.view_menu import populate_view_menu
from Imervue.paint.workspace_autosave import AutosaveMixin
from Imervue.paint.workspace_content import ContentOpsMixin
from Imervue.paint.workspace_docks import DockBuilder, DockLayoutMixin
from Imervue.paint.workspace_shortcuts import ShortcutMixin
from Imervue.paint.workspace_status import StatusLineMixin
from Imervue.paint.workspace_tabs import TabManagerMixin

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


logger = logging.getLogger("Imervue.paint.workspace")

# Tool handlers that accept a back-reference to the workspace so they can
# read / write shared workspace state (bezier path, transform box, …).
_WORKSPACE_AWARE_TOOLS = (
    "bezier_pen", "transform", "crop",
    "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
)


class PaintWorkspace(  # noqa: PLR0904 - thin coordinator over focused mixins
    AutosaveMixin,
    TabManagerMixin,
    DockLayoutMixin,
    ContentOpsMixin,
    StatusLineMixin,
    ShortcutMixin,
    QMainWindow,
):
    """Assembles the Paint tab from the toolbar + canvas + dock pieces."""

    def __init__(self, state: ToolState | None = None, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._state = state if state is not None else ts.load_tool_state()
        self._seed_default_brush_presets()
        self._build_menu_bar()
        self._build_status_bar()
        self._init_workspace_slots()
        self._build_toast()
        self._build_tab_strip()
        self._build_toolbars()
        DockBuilder(self).build()
        self._build_size_hud()
        self._wire_canvas_signals()
        self._build_navigator_throttle()
        self._build_dispatcher()
        self._finish_construction()

    # ---- construction helpers ------------------------------------------

    def _seed_default_brush_presets(self) -> None:
        """Seed the full-featured default brush preset pack on first launch.

        Idempotent: when the user already has at least one brush sub-tool
        the seeder bails out, so existing users keep their saved presets
        and tests that build their own state are unaffected.
        """
        from Imervue.paint.default_brush_presets import seed_default_brush_presets
        seed_default_brush_presets(self._state)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._build_zoom_indicator()

    def _init_workspace_slots(self) -> None:
        """Initialise the plain-data slots the mixins read from."""
        # Cached most-recent cursor position in image space so the status
        # line can re-render after a tool / brush / selection change.
        self._last_hover: tuple[int, int] | None = None
        # Per-tab "modified since last save" flag, keyed by canvas widget.
        self._tab_dirty: dict = {}
        # ``time.monotonic()`` of the most recent successful autosave, or
        # ``None`` while the workspace has never autosaved.
        self._last_autosave_at: float | None = None

    def _build_toast(self) -> None:
        from Imervue.gui.toast import ToastManager
        self.toast = ToastManager(self)

    def _build_tab_strip(self) -> None:
        """Central canvas tab strip, seeded with one blank paintable tab.

        ``self._canvas`` always points at the active tab's canvas;
        switching tabs reassigns it via :meth:`_on_tab_changed`.
        ``currentChanged`` is wired later (after the dispatcher exists)
        so the signal doesn't fire into a half-built workspace.
        """
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tabs.tabBar().installEventFilter(self)
        self._install_new_tab_corner_button()
        self.setCentralWidget(self._tabs)
        self._canvas = PaintCanvas(self)
        self._canvas.new_blank_document()
        self._tabs.addTab(self._canvas, self._next_untitled_tab_name())

    def _build_toolbars(self) -> None:
        self._options_bar = PaintOptionsBar(self._state, self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._options_bar)
        self._tool_bar = PaintToolBar(self._state, self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._tool_bar)

    def _build_size_hud(self) -> None:
        from Imervue.paint.size_hud import SizeHudState
        self._size_hud = SizeHudState()
        if hasattr(self._canvas, "set_size_hud"):
            self._canvas.set_size_hud(self._size_hud, self._state)

    def _wire_canvas_signals(self) -> None:
        """Wire status-bar hover, tool cursor, navigator + context menu."""
        self._canvas.hover_changed.connect(self._on_hover_changed)
        self._canvas.image_loaded.connect(self._on_image_loaded)
        self._navigator_dock.zoom_changed.connect(self._canvas.set_zoom)
        self._navigator_dock.fit_requested.connect(self._canvas.reset_view)
        self._canvas.zoom_changed.connect(self._navigator_dock.set_zoom)
        self._canvas.zoom_changed.connect(self._on_zoom_changed_refresh_cursor)
        self._canvas.customContextMenuRequested.connect(
            self._show_canvas_context_menu,
        )

    def _build_navigator_throttle(self) -> None:
        """Coalesce navigator-preview rebuilds to ~6 fps.

        ``document_changed`` fires on every brush dab; rebuilding the
        QPixmap each time would double the per-stroke cost.
        """
        self._nav_dirty = False
        self._nav_timer = QTimer(self)
        self._nav_timer.setSingleShot(True)
        self._nav_timer.setInterval(160)
        self._nav_timer.timeout.connect(self._refresh_navigator_preview)
        self._canvas.document_changed.connect(self._on_document_changed)
        self._refresh_navigator_preview()
        self._navigator_dock.set_zoom(self._canvas.zoom_factor())

    def _build_dispatcher(self) -> None:
        """Build the tool dispatcher + undo stack and attach the
        workspace-aware tool handlers.

        Dispatcher providers are wrapped in lambdas so they always read
        from the *current* active canvas — without this indirection a
        tab switch would leave the dispatcher talking to the previous
        tab's pixel buffer.
        """
        from Imervue.paint.undo_stack import UndoStack
        self._undo_stack = UndoStack(self._canvas.document())
        self._dispatcher = ToolDispatcher(
            self._state,
            image_provider=lambda: self._canvas.current_image(),
            selection_provider=lambda: self._canvas.current_selection(),
            set_selection=lambda mask: self._canvas.set_selection(mask),
            parent_widget=self,
            reference_provider=lambda: self._canvas.document().reference_layer_image(),
            composite_provider=lambda: self._canvas.document().composite(),
            overlay_setter=lambda overlay: self._canvas.set_tool_overlay(overlay),
            commit_undo=self._on_dispatcher_commit,
        )
        self._canvas.set_tool_dispatcher(self._dispatcher)
        self._attach_workspace_aware_tools()

    def _attach_workspace_aware_tools(self) -> None:
        """Hand each workspace-aware tool a back-reference to ``self``.

        Lazy-attach pattern: tools that need shared workspace state
        (bezier path, transform box, crop document, shape snapping)
        expose ``attach_workspace``; the dispatcher built them without
        that knowledge in ``_build_handlers``.
        """
        handlers = self._dispatcher._handlers  # noqa: SLF001
        for key in _WORKSPACE_AWARE_TOOLS:
            tool = handlers.get(key)
            if tool is not None and hasattr(tool, "attach_workspace"):
                tool.attach_workspace(self)

    def _finish_construction(self) -> None:
        """Final wiring once every collaborator exists."""
        self._unsubscribe = self._state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._refresh_cursor_for_tool()
        # Now safe to wire tab-change re-binding — every dock and the
        # dispatcher have been constructed above.
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._build_welcome_hint()
        self._maybe_offer_autosave_recovery()
        self._build_brush_kind_shortcuts()

    # ---- public ----------------------------------------------------------

    def canvas(self) -> PaintCanvas:
        return self._canvas

    def state(self) -> ToolState:
        return self._state

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Save the dock layout before the window goes away, and block
        the close on unsaved tabs.

        The per-tab close handler already protects single-tab discards;
        this branch covers the wider "user clicks the window X with
        five modified tabs" case where each tab would otherwise be
        thrown away silently.
        """
        if self._has_unsaved_tabs() and not self._confirm_discard_all_unsaved():
            event.ignore()
            return
        import contextlib
        with contextlib.suppress(RuntimeError, OSError):
            self._save_dock_state()
        super().closeEvent(event)

    # ---- drag-and-drop file open ---------------------------------------

    SUPPORTED_DROP_EXTS = (
        ".psd", ".png", ".jpg", ".jpeg", ".tif", ".tiff",
        ".bmp", ".webp",
    )

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Accept file URL drops the workspace knows how to open."""
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        for url in mime.urls():
            if url.isLocalFile() and self._is_supported_drop(url.toLocalFile()):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        # Mirror dragEnter — Qt requires both for a clean drop visual.
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Open every supported file the user dropped.

        PSDs route through the file-menu bridge so the open feeds the
        recent-files list. Plain raster files are loaded into the active
        canvas via load_image — same path as the existing File ▸ Open
        flow for non-PSDs.
        """
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        opened_any = False
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if not self._is_supported_drop(path):
                continue
            self._open_dropped_path(path)
            opened_any = True
        if opened_any:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _is_supported_drop(self, path: str) -> bool:
        lowered = path.lower()
        return any(lowered.endswith(ext) for ext in self.SUPPORTED_DROP_EXTS)

    def _open_dropped_path(self, path: str) -> None:
        if path.lower().endswith(".psd"):
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "open_psd_at"):
                bridge.open_psd_at(path)
                return
        # Plain raster: load via Pillow, push into the active canvas.
        try:
            from PIL import Image
            with Image.open(path) as img:
                rgba = np.array(img.convert("RGBA"), dtype=np.uint8)
            self._canvas.load_image(rgba)
            from Imervue.paint import recent_files
            recent_files.add(path)
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "refresh_recent_menu"):
                bridge.refresh_recent_menu()
        except (OSError, ValueError) as exc:
            logger.warning("dropped file %r could not be opened: %s", path, exc)

    # ---- undo / redo + history feedback --------------------------------

    def _on_dispatcher_commit(self) -> None:
        """Push an undo snapshot after the dispatcher commits a stroke.

        Called by the dispatcher only at gesture boundaries so a long
        brush stroke counts as one undoable action rather than every
        dab. Also flips the active tab to "modified".
        """
        self._undo_stack.commit()
        self._set_tab_dirty(self._canvas, True)

    def undo(self) -> None:
        """Undo the most recent committed stroke if there is one."""
        if self._undo_stack.undo():
            self._canvas.invalidate_texture()
            self._canvas.update()
            self._notify_history_action("undo")
        else:
            self._notify_history_empty("undo")

    def redo(self) -> None:
        """Re-apply the most recently undone stroke."""
        if self._undo_stack.redo():
            self._canvas.invalidate_texture()
            self._canvas.update()
            self._notify_history_action("redo")
        else:
            self._notify_history_empty("redo")

    def _notify_history_action(self, kind: str) -> None:
        """Toast a confirmation after a successful undo / redo.

        Surfaces the action *and* the remaining depth so the user can
        pace their Ctrl+Z taps without overshooting.
        """
        lang = language_wrapper.language_word_dict
        verb = lang.get(f"paint_history_{kind}", kind.title())
        depth = self._history_depth_for(kind)
        msg = lang.get(
            "paint_history_done", "{verb} ({depth} left)",
        ).format(verb=verb, depth=depth)
        self._broadcast_history_msg(msg, level="info")

    def _notify_history_empty(self, kind: str) -> None:
        lang = language_wrapper.language_word_dict
        msg = lang.get(
            f"paint_history_{kind}_empty",
            "Nothing to {kind}",
        ).format(kind=kind)
        self._broadcast_history_msg(msg, level="warning")

    def _history_depth_for(self, kind: str) -> int:
        """Return how many steps remain in the requested direction.

        Falls back to ``0`` rather than crashing if the underlying
        :class:`UndoStack` doesn't expose the queried side.
        """
        if kind == "undo":
            stack = getattr(self._undo_stack, "_undo", ())
        else:
            stack = getattr(self._undo_stack, "_redo", ())
        return len(stack) if stack is not None else 0

    def _broadcast_history_msg(self, msg: str, *, level: str) -> None:
        toast = getattr(self, "toast", None)
        if toast is not None:
            target = getattr(toast, level, None)
            if callable(target):
                target(msg)
                return
        status = getattr(self, "_status", None)
        if status is not None:
            status.showMessage(msg, 2000)

    # ---- load image -----------------------------------------------------

    def load_image(self, arr) -> None:
        """Forward an HxWx4 RGBA buffer to the central canvas.

        ``None`` resets to a fresh blank canvas — never to an empty
        document. The Paint workspace is always for painting, so the
        invariant "there is always a layer to paint on" must hold even
        when the host main window passes ``None``.
        """
        if arr is None:
            self._canvas.new_blank_document()
        else:
            self._canvas.load_image(arr)
        # The canvas swapped its PaintDocument; rebind the layer dock
        # so it re-subscribes and refreshes against the new stack.
        self._layer_dock.set_document(self._canvas.document())

    # ---- cursor + tool-state events ------------------------------------

    # Tools whose cursor is the full-featured brush ring (diameter
    # tracks size × zoom).
    _BRUSH_RING_TOOLS = frozenset({
        "brush", "eraser", "smudge", "blur", "clone_stamp",
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

    # ---- canvas context menu -------------------------------------------

    def _show_canvas_context_menu(self, pos) -> None:
        """Pop a raster-editor quick-actions menu at the right-click
        position. Construction is delegated to
        :meth:`_build_canvas_context_menu` so tests can verify the action
        set without driving Qt's modal loop."""
        menu = self._build_canvas_context_menu()
        menu.exec(self._canvas.mapToGlobal(pos))

    def _build_canvas_context_menu(self):
        """Return the QMenu that ``_show_canvas_context_menu`` pops.

        Surfaces the keyboard-frequent actions (undo / redo / select all
        / deselect / fit / 100 %). Each entry is wired to the same
        workspace methods the menu / shortcut invokes.
        """
        from PySide6.QtWidgets import QMenu
        lang = language_wrapper.language_word_dict
        menu = QMenu(self._canvas)
        undo_action = menu.addAction(lang.get("paint_edit_undo", "Undo"))
        undo_action.triggered.connect(self.undo)
        undo_action.setEnabled(self._undo_stack.can_undo())
        redo_action = menu.addAction(lang.get("paint_edit_redo", "Redo"))
        redo_action.triggered.connect(self.redo)
        redo_action.setEnabled(self._undo_stack.can_redo())
        menu.addSeparator()
        select_all = menu.addAction(
            lang.get("paint_edit_select_all", "Select All"),
        )
        select_all.triggered.connect(self._select_all_canvas)
        deselect = menu.addAction(
            lang.get("paint_edit_deselect", "Deselect"),
        )
        deselect.triggered.connect(self._deselect_canvas)
        deselect.setEnabled(self._has_active_selection())
        menu.addSeparator()
        fit = menu.addAction(lang.get("paint_view_fit", "Fit to Window"))
        fit.triggered.connect(self._canvas.reset_view)
        zoom_100 = menu.addAction(lang.get("paint_view_100", "100 %"))
        zoom_100.triggered.connect(lambda: self._canvas.set_zoom(1.0))
        return menu

    def _select_all_canvas(self) -> None:
        document = self._canvas.document()
        shape = getattr(document, "shape", None)
        if shape is None:
            return
        h, w = shape
        mask = np.ones((h, w), dtype=bool)
        if hasattr(document, "set_selection"):
            document.set_selection(mask)
            self._canvas.update()

    def _deselect_canvas(self) -> None:
        document = self._canvas.document()
        if hasattr(document, "set_selection"):
            document.set_selection(None)
            self._canvas.update()

    def _has_active_selection(self) -> bool:
        document = self._canvas.document()
        if not hasattr(document, "selection"):
            return False
        sel = document.selection()
        return sel is not None and bool(sel.any())

    # ---- tab strip corner button + event filter ------------------------

    def _install_new_tab_corner_button(self) -> None:
        """Mount a small "+" button in the tab strip's right corner so
        the artist has a one-click affordance for ``new_tab``."""
        from PySide6.QtWidgets import QToolButton
        lang = language_wrapper.language_word_dict
        self._new_tab_btn = QToolButton(self._tabs)
        self._new_tab_btn.setText("+")
        self._new_tab_btn.setAutoRaise(True)
        self._new_tab_btn.setToolTip(
            lang.get("paint_tab_new_tooltip", "New tab (Ctrl+T)"),
        )
        self._new_tab_btn.clicked.connect(self.new_tab)
        self._tabs.setCornerWidget(self._new_tab_btn, Qt.Corner.TopRightCorner)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if (
            hasattr(self, "_welcome_hint")
            and obj is self._canvas
            and event.type() == event.Type.Resize
            and self._welcome_hint.isVisible()
        ):
            self._welcome_hint.position_centred(
                self._canvas.width(), self._canvas.height(),
            )
        if obj is self._tabs.tabBar() and self._handle_tab_bar_event(event):
            return True
        return super().eventFilter(obj, event)

    def _handle_tab_bar_event(self, event) -> bool:
        """Forward middle-click on the tab bar to ``close_tab``.

        Returns ``True`` when the event is consumed so Qt doesn't also
        dispatch it as a tab activate.
        """
        if event.type() != event.Type.MouseButtonRelease:
            return False
        if event.button() != Qt.MouseButton.MiddleButton:
            return False
        pos = event.position() if hasattr(event, "position") else event.pos()
        index = self._tabs.tabBar().tabAt(pos.toPoint())
        if index < 0:
            return False
        self.close_tab(index)
        return True

    # ---- menu bar -------------------------------------------------------

    def _build_menu_bar(self) -> None:
        """Construct the embedded menu bar and populate every section.

        Ordering matches the original File → Edit → Image → Layer → View
        → Tools → Manga → Settings layout the artists are used to.
        """
        self.setMenuBar(build_paint_menu_bar(self))
        populate_file_menu(self)
        populate_edit_menu(self)
        populate_image_menu(self)
        populate_layer_menu(self)
        populate_view_menu(self)
        populate_tools_menu(self)
        populate_manga_menu(self)
        populate_settings_menu(self)

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

    # ---- compatibility shim ---------------------------------------------

    @staticmethod
    def cursor_for_tool(tool: str) -> Qt.CursorShape:
        """Re-exported for callers that don't want to import canvas."""
        return cursor_for_tool(tool)
