"""Top-level Paint workspace widget.

A QMainWindow used as the centralWidget of a QTabWidget page. Embedding
a QMainWindow inside another QMainWindow is unusual but well-supported
by Qt and is the simplest way to host real QDockWidgets — the alternative
(plain QSplitter layout) loses floating / re-docking / collapse-arrow
behaviour that users expect from raster paint apps and PS-style apps.

Layout:

* Top: PaintOptionsBar — context-sensitive options strip.
* Left: PaintToolBar — scrollable two-column icon palette in a movable toolbar.
* Centre: PaintCanvas — the GL drawing surface.
* Right: a full-height tabbed inspector, with Color, Brush, Layers and Materials
  first. The Window menu groups all fourteen panels by workflow.

The class is a thin coordinator: construction is delegated to
:class:`~Imervue.paint.workspace_docks.DockBuilder`, and the behaviour
clusters (autosave, tabs, docks, content ops, status line, shortcuts)
live in the focused mixins it composes: drag-drop open
(:mod:`workspace_drop`), per-canvas undo / redo (:mod:`workspace_undo`),
cursor / state-event / navigator handlers (:mod:`workspace_canvas_events`),
the canvas context menu (:mod:`workspace_canvas_menu`) and the tab-strip
event filter (:mod:`workspace_tab_strip`). This module keeps the
construction order, the canvas / dispatcher wiring, image loading, the
close protocol and the menu bar.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

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
from Imervue.paint.tool_dispatcher import DispatcherHooks, ToolDispatcher
from Imervue.paint.tools_menu import populate_tools_menu
from Imervue.paint.view_menu import populate_view_menu
from Imervue.paint.workspace_autosave import AutosaveMixin
from Imervue.paint.workspace_canvas_events import CanvasEventsMixin
from Imervue.paint.workspace_canvas_menu import CanvasMenuMixin
from Imervue.paint.workspace_content import ContentOpsMixin
from Imervue.paint.workspace_docks import DockBuilder, DockLayoutMixin
from Imervue.paint.workspace_drop import FileDropMixin
from Imervue.paint.workspace_shortcuts import ShortcutMixin
from Imervue.paint.workspace_status import StatusLineMixin
from Imervue.paint.workspace_tab_strip import TabStripMixin
from Imervue.paint.workspace_tabs import TabManagerMixin
from Imervue.paint.workspace_undo import UndoHistoryMixin, _pointer_button_held
from Imervue.system.best_effort import best_effort
from Imervue.gui.control_tooltips import enable_control_tooltips

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


# ``_pointer_button_held`` moved to workspace_undo; re-exported here for callers.
__all__ = ["PaintWorkspace", "_pointer_button_held"]

logger = logging.getLogger("Imervue.paint.workspace")

# Tool handlers that accept a back-reference to the workspace so they can
# read / write shared workspace state (bezier path, transform box, …).
_WORKSPACE_AWARE_TOOLS = (
    "bezier_pen", "transform", "crop",
    "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
)


class PaintWorkspace(  # noqa: PLR0904 - thin coordinator over focused mixins
    FileDropMixin,
    UndoHistoryMixin,
    CanvasEventsMixin,
    CanvasMenuMixin,
    TabStripMixin,
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
        if parent is not None:
            # QMainWindow keeps Qt.Window even with a parent; a same-parent
            # layout.addWidget() does not reparent it or clear that flag.
            self.setWindowFlags(Qt.WindowType.Widget)
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
        enable_control_tooltips(self)

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
        # Native tab notifications must not reacquire a wrapper from inside the filter.
        self._canvas_tab_bar = self._tabs.tabBar()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self._canvas_tab_bar.installEventFilter(self)
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
        # One undo stack per canvas (keyed by the canvas), resolved lazily by
        # the ``_undo_stack`` property. A single shared stack stayed bound to the
        # first document forever, so after a tab switch / open Ctrl+Z applied one
        # document's history to another — a silent, destructive corruption.
        self._undo_stacks: dict = {}
        # Seed the initial canvas's stack now so its baseline is the blank canvas
        # and the very first stroke is undoable (see _ensure_undo_stack).
        self._ensure_undo_stack()
        self._dispatcher = ToolDispatcher(
            self._state,
            image_provider=lambda: self._canvas.current_image(),
            hooks=DispatcherHooks(
                selection_provider=lambda: self._canvas.current_selection(),
                set_selection=lambda mask: self._canvas.set_selection(mask),
                parent_widget=self,
                reference_provider=(
                    lambda: self._canvas.document().reference_layer_image()),
                composite_provider=lambda: self._canvas.document().composite(),
                panel_layout_provider=self._panel_layout,
                overlay_setter=lambda overlay: self._canvas.set_tool_overlay(overlay),
                commit_undo=self._on_dispatcher_commit,
            ),
        )
        self._canvas.set_tool_dispatcher(self._dispatcher)
        self._attach_workspace_aware_tools()

    def _panel_layout(self):
        """The current document's Panel Cutter layout, if it still fits its canvas."""
        from Imervue.paint.manga_panels import layout_for_canvas
        document = self._canvas.document()
        if document.shape is None:
            return None
        return layout_for_canvas(getattr(document, "panel_layout", None), document.shape)

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
        self._layer_dock.edit_committed.connect(self._on_dispatcher_commit)
        self._unsubscribe = self._state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._refresh_cursor_for_tool()
        # Now safe to wire tab-change re-binding — every dock and the
        # dispatcher have been constructed above.
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._build_welcome_hint()
        self._maybe_offer_autosave_recovery()
        self.start_autosave()
        self._build_brush_kind_shortcuts()
        from Imervue.paint.shortcut_registry import load_shortcuts
        self.apply_shortcut_registry(load_shortcuts())

    # ---- public ----------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if getattr(self, "_initial_dock_size_pending", False):
            from Imervue.system.qt_timers import call_later
            self._initial_dock_size_pending = False
            # Nested tab/dock layouts finish polishing after the first show.
            call_later(50, self, self._size_default_inspector)

    def canvas(self) -> PaintCanvas:
        return self._canvas

    def state(self) -> ToolState:
        return self._state

    def confirm_close(self) -> bool:
        """Ask about unsaved tabs; True when the workspace may go away.

        On True it has stopped autosaving, saved the dock layout and deleted
        its own autosave snapshots (nothing is left to recover). The main
        window calls this before closing: as a tab page this widget never
        gets a ``closeEvent`` of its own, so unsaved tabs used to vanish.
        """
        if self._has_unsaved_tabs() and not self._confirm_discard_all_unsaved():
            return False
        import contextlib
        # Stop the autosave timer so a queued tick can't fire on the torn-down
        # canvas after close.
        with best_effort("stop the autosave timer", logger):
            self.stop_autosave()
        with best_effort("delete this workspace's autosave snapshots", logger):
            self.discard_own_autosaves()
        with contextlib.suppress(RuntimeError, OSError):
            self._save_dock_state()
        return True

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Block the close on unsaved tabs (see :meth:`confirm_close`)."""
        if not self.confirm_close():
            event.ignore()
            return
        super().closeEvent(event)

    # ---- load image -----------------------------------------------------

    def load_image(self, arr, *, source_path: str = "") -> None:
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
        self._ensure_undo_stack()
        from Imervue.paint.document_status import document_status, refresh_document_status
        document_status(self._canvas).source = str(source_path)
        refresh_document_status(self, self._canvas)

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

    # ---- compatibility shim ---------------------------------------------

    @staticmethod
    def cursor_for_tool(tool: str) -> Qt.CursorShape:
        """Re-exported for callers that don't want to import canvas."""
        return cursor_for_tool(tool)
