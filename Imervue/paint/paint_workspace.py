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
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

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
        populate_edit_menu(self)
        populate_image_menu(self)
        populate_layer_menu(self)
        populate_view_menu(self)
        populate_tools_menu(self)
        populate_manga_menu(self)
        populate_settings_menu(self)

        # Status bar shows the cursor's image-space coordinates while painting.
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)

        # Central canvas tab strip — each tab owns one PaintCanvas + its
        # own PaintDocument so the user can keep multiple drawings open
        # at once. ``self._canvas`` always points at the *active* tab's
        # canvas; switching tabs reassigns it via :meth:`_on_tab_changed`.
        # Seeded with one blank tab so the workspace is immediately
        # paintable just like the pre-tab version.
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        # ``currentChanged`` is wired AFTER ``_dispatcher`` is built —
        # otherwise the signal fires during ``addTab`` below and the
        # handler trips over the missing dispatcher attribute.
        self.setCentralWidget(self._tabs)
        self._canvas = PaintCanvas(self)
        self._canvas.new_blank_document()
        self._tabs.addTab(self._canvas, self._next_untitled_tab_name())

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
        # Seed the material dock with the procedural catalog so the
        # user has tones / textures / patterns out of the box without
        # having to point the library at any folder. A future per-user
        # library setting can override this via ``set_index``.
        from Imervue.paint.material_library import default_material_index
        self._material_dock = MaterialDock(
            index=default_material_index(), parent=self,
        )
        # Swatch dock — floating, free-form recent-colour grid bound
        # to the same ToolState as the colour dock.
        from Imervue.paint.swatch_panel import SwatchPanel
        self._swatch_dock = SwatchPanel(self._state, self)
        self._swatch_dock.color_chosen.connect(
            lambda r, g, b: self._state.set_foreground((r, g, b), commit=False),
        )

        # Reference dock — pinned reference image with independent
        # pan/zoom, useful when copying a pose / lighting reference.
        from Imervue.paint.reference_dock import ReferenceDock
        self._reference_dock = ReferenceDock(self)

        # Histogram dock — RGB / luma bin counts of the active doc.
        from Imervue.paint.histogram_dock import HistogramDock
        self._histogram_dock = HistogramDock(self)

        # Animation timeline dock — frame snapshots + transport.
        # The dock owns the AnimationTimeline; the workspace listens
        # to its signals to push frames onto the active canvas.
        from Imervue.paint.animation_dock import AnimationDock
        self._animation_dock = AnimationDock(parent=self)
        self._animation_dock.add_frame_requested.connect(
            self._on_animation_add_frame,
        )
        self._animation_dock.remove_frame_requested.connect(
            self._on_animation_remove_frame,
        )
        self._animation_dock.frame_selected.connect(
            self._on_animation_frame_selected,
        )

        for dock in (
            self._color_dock,
            self._brush_dock,
            self._layer_dock,
            self._navigator_dock,
            self._material_dock,
            self._history_dock,
            self._swatch_dock,
            self._reference_dock,
            self._animation_dock,
            self._histogram_dock,
        ):
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            dock.setFeatures(
                dock.features()
                | dock.DockWidgetFeature.DockWidgetMovable
                | dock.DockWidgetFeature.DockWidgetFloatable,
            )

        # Window menu — toggle each dock's visibility from the
        # workspace's menu bar so the user can hide / show panels
        # without right-clicking the toolbar.
        self._populate_window_menu()

        # Brush-size HUD overlay — bracket-key bindings flash a ring
        # at the canvas centre via the SizeHudState helper.
        from Imervue.paint.size_hud import SizeHudState
        self._size_hud = SizeHudState()
        if hasattr(self._canvas, "set_size_hud"):
            self._canvas.set_size_hud(self._size_hud, self._state)

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
        # Dispatcher providers are deliberately wrapped in lambdas so
        # they always read from the *current* active canvas — without
        # this indirection a tab switch would leave the dispatcher
        # talking to the previous tab's pixel buffer.
        self._dispatcher = ToolDispatcher(
            self._state,
            image_provider=lambda: self._canvas.current_image(),
            selection_provider=lambda: self._canvas.current_selection(),
            set_selection=lambda mask: self._canvas.set_selection(mask),
            parent_widget=self,
            reference_provider=lambda: self._canvas.document().reference_layer_image(),
            composite_provider=lambda: self._canvas.document().composite(),
        )
        self._canvas.set_tool_dispatcher(self._dispatcher)
        # Bezier pen needs a workspace handle so it can read / write
        # the shared BezierPath stored on the workspace; the dispatcher
        # built it without that knowledge in _build_handlers().
        pen_tool = self._dispatcher._handlers.get("bezier_pen")  # noqa: SLF001
        if pen_tool is not None and hasattr(pen_tool, "attach_workspace"):
            pen_tool.attach_workspace(self)
        # Transform-handle tool reads / writes the workspace's shared
        # ``_transform_box`` so pointer state survives across events.
        transform_tool = self._dispatcher._handlers.get("transform")  # noqa: SLF001
        if (
            transform_tool is not None
            and hasattr(transform_tool, "attach_workspace")
        ):
            transform_tool.attach_workspace(self)
        # Crop tool needs the workspace so it can resolve to the
        # active tab's PaintDocument and invoke ``document.crop``.
        crop_tool = self._dispatcher._handlers.get("crop")  # noqa: SLF001
        if (
            crop_tool is not None
            and hasattr(crop_tool, "attach_workspace")
        ):
            crop_tool.attach_workspace(self)

        self._unsubscribe = self._state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._refresh_cursor_for_tool()

        # Now safe to wire tab-change re-binding — every dock and the
        # dispatcher have been constructed above.
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ---- public ----------------------------------------------------------

    def canvas(self) -> PaintCanvas:
        return self._canvas

    def state(self) -> ToolState:
        return self._state

    # ---- secondary views -----------------------------------------------

    def open_secondary_view(self):
        """Spawn an independent overview window onto the same composite.

        Multiple secondary views can be opened — each one tracks the
        same composite + auto-removes itself from the workspace's
        view list when its window is closed.
        """
        return self._open_secondary_view(mirror_horizontal=False)

    def open_mirror_preview(self):
        """Spawn a horizontally-flipped read-only preview window.

        Same plumbing as :meth:`open_secondary_view`; the flip is a
        view-only transform on the composite so the underlying
        document is unaffected. The "anatomy check" workflow — drawing
        a face / pose and looking at it mirrored to spot asymmetry.
        """
        return self._open_secondary_view(mirror_horizontal=True)

    def open_tile_preview(self):
        """Spawn a 3×3 tiled preview window for seamless-tile checking.

        The composite is rendered as a tiled grid so the artist can
        verify the canvas wraps cleanly on every edge — the texture-
        artist workflow MediBang lacks but Photoshop / Krita expose.
        """
        return self._open_secondary_view(tile_preview=True)

    def _open_secondary_view(
        self, *,
        mirror_horizontal: bool = False,
        tile_preview: bool = False,
    ):
        from Imervue.paint.multi_view import SecondaryView, composite_to_pixmap
        view = SecondaryView(
            self,
            mirror_horizontal=mirror_horizontal,
            tile_preview=tile_preview,
        )
        if not hasattr(self, "_secondary_views"):
            self._secondary_views = []
        self._secondary_views.append(view)
        view.closed.connect(lambda v=view: self._on_secondary_view_closed(v))
        # Seed with the current composite so the new window has
        # something to render before the next document change.
        composite = self._canvas.document().composite()
        view.set_composite(composite_to_pixmap(composite))
        view.show()
        return view

    def secondary_view_count(self) -> int:
        return len(getattr(self, "_secondary_views", ()))

    def _on_secondary_view_closed(self, view) -> None:
        if hasattr(self, "_secondary_views") and view in self._secondary_views:
            self._secondary_views.remove(view)

    def _push_composite_to_secondary_views(self, composite) -> None:
        from Imervue.paint.multi_view import composite_to_pixmap
        views = getattr(self, "_secondary_views", ())
        if not views:
            return
        pixmap = composite_to_pixmap(composite)
        for view in views:
            view.set_composite(pixmap)

    # ---- autosave -------------------------------------------------------

    def start_autosave(
        self, *, interval_sec: int | None = None, target_dir=None,
    ) -> None:
        """Start the periodic snapshot timer.

        Cheap to call repeatedly — a second call replaces the existing
        timer interval rather than stacking timers. Pulled out as an
        explicit method (not ctor wiring) so tests can opt out and
        keep workspace construction cheap.
        """
        from Imervue.paint.autosave import DEFAULT_INTERVAL_SEC
        seconds = int(interval_sec or DEFAULT_INTERVAL_SEC)
        self._autosave_target_dir = target_dir
        if not hasattr(self, "_autosave_timer"):
            self._autosave_timer = QTimer(self)
            self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self._autosave_timer.start(max(1000, seconds * 1000))

    def stop_autosave(self) -> None:
        if hasattr(self, "_autosave_timer"):
            self._autosave_timer.stop()

    def take_autosave_snapshot_now(self):
        """Force an immediate snapshot — returns the snapshot path or
        ``None`` if there's nothing to save yet."""
        from Imervue.paint.autosave import take_snapshot
        composite = self._canvas.document().composite()
        if composite is None:
            return None
        target = getattr(self, "_autosave_target_dir", None)
        try:
            return take_snapshot(composite, target_dir=target)
        except (OSError, ValueError):
            return None

    def restore_latest_autosave(self, *, target_dir=None) -> bool:
        """Load the most-recent autosave PNG into the active canvas.

        Returns ``True`` when a snapshot was found and pasted; the
        caller drives the user-visible "restore?" prompt around this.
        """
        from Imervue.paint.autosave import latest_snapshot, load_snapshot
        path = latest_snapshot(target_dir=target_dir)
        if path is None:
            return False
        try:
            arr = load_snapshot(path)
        except (OSError, ValueError):
            return False
        self.load_image(arr)
        return True

    def _on_autosave_tick(self) -> None:
        self.take_autosave_snapshot_now()

    # ---- animation timeline --------------------------------------------

    def _on_animation_add_frame(self) -> None:
        """Snapshot the active canvas composite and append it to the
        animation timeline as a fresh frame."""
        composite = self._canvas.document().composite()
        if composite is None:
            return
        timeline = self._animation_dock.timeline()
        timeline.add_frame(composite)
        self._animation_dock.refresh()
        self._refresh_onion_skin_source()

    def _on_animation_remove_frame(self, index: int) -> None:
        timeline = self._animation_dock.timeline()
        if timeline.remove_frame(index):
            self._animation_dock.refresh()
            self._refresh_onion_skin_source()

    def _on_animation_frame_selected(self, index: int) -> None:
        """Load the selected frame's image into the active layer.

        Treats the active layer as the "current frame canvas" — the
        user picks frames; we paste them. Existing layer pixels are
        replaced. Onion-skin source is refreshed so the previous
        frame ghost stays current.
        """
        timeline = self._animation_dock.timeline()
        frame = timeline.frame_at(index)
        if frame is None:
            return
        document = self._canvas.document()
        layer = document.active_layer()
        if layer is None or layer.image.shape != frame.image.shape:
            return
        np.copyto(layer.image, frame.image)
        document.invalidate_composite()
        self._canvas.update()
        self._refresh_onion_skin_source()

    def _refresh_onion_skin_source(self) -> None:
        """Point the canvas onion-skin overlay at the previous frame."""
        if not hasattr(self._canvas, "set_onion_skin_source"):
            return
        timeline = self._animation_dock.timeline()
        prev = timeline.previous_frame()
        if prev is None:
            self._canvas.set_onion_skin_source(None)
            return
        # The canvas accepts a zero-arg callable that returns the
        # buffer (the same protocol the existing 22d hook already
        # uses), so wrap our cached reference in a thunk.
        buffer = prev.image
        self._canvas.set_onion_skin_source(lambda: buffer)

    # ---- quick mask mode -----------------------------------------------

    def is_quick_mask_active(self) -> bool:
        return getattr(self, "_quick_mask_state", None) is not None

    def enter_quick_mask(self) -> bool:
        """Toggle the active layer into a paintable selection overlay.

        Returns ``True`` if the mode was entered. Refuses gracefully
        when there's no active layer (the user has nothing to paint
        on); the caller can ignore the return.
        """
        if self.is_quick_mask_active():
            return False
        from Imervue.paint.quick_mask import enter_mode
        canvas = self.canvas()
        document = canvas.document()
        layer = document.active_layer()
        if layer is None:
            return False
        layer_index = document._active_index   # noqa: SLF001
        state = enter_mode(
            layer.image, document.selection(), layer_index=layer_index,
        )
        # Swap the layer's pixels for the proxy buffer so brushes paint
        # into the overlay rather than the underlying art.
        layer.image = state.buffer
        self._quick_mask_state = state
        document.invalidate_composite()
        canvas.update()
        return True

    def exit_quick_mask(self) -> bool:
        """Convert the painted overlay back into a selection and
        restore the layer's original pixels."""
        if not self.is_quick_mask_active():
            return False
        from Imervue.paint.quick_mask import exit_mode
        state = self._quick_mask_state   # noqa: SLF001
        canvas = self.canvas()
        document = canvas.document()
        if state.layer_index < 0 or state.layer_index >= document.layer_count:
            # The active layer disappeared while in quick-mask mode;
            # drop the state without touching anything.
            self._quick_mask_state = None
            return False
        layer = document.layer_at(state.layer_index)
        restored, selection = exit_mode(state)
        layer.image = restored
        canvas.set_selection(selection)
        self._quick_mask_state = None
        document.invalidate_composite()
        canvas.update()
        return True

    # ---- multi-document tabs --------------------------------------------

    def tab_count(self) -> int:
        """Return how many open documents the workspace currently holds."""
        return self._tabs.count()

    def new_tab(self) -> PaintCanvas:
        """Open a fresh blank document in a new tab and switch to it.

        Returns the new tab's :class:`PaintCanvas` so callers can
        e.g. ``load_image`` into it. The dispatcher follows because
        its providers read from ``self._canvas`` at event time.
        """
        canvas = PaintCanvas(self)
        canvas.new_blank_document()
        canvas.set_tool_dispatcher(self._dispatcher)
        idx = self._tabs.addTab(canvas, self._next_untitled_tab_name())
        self._tabs.setCurrentIndex(idx)
        return canvas

    def close_tab(self, index: int) -> bool:
        """Close the tab at ``index``. Returns ``True`` on success.

        Refuses to close the last remaining tab — the workspace
        always needs at least one paintable canvas, mirroring the
        single-tab invariant from before tabs existed.
        """
        if index < 0 or index >= self._tabs.count():
            return False
        if self._tabs.count() <= 1:
            return False
        widget = self._tabs.widget(index)
        self._tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        return True

    def _next_untitled_tab_name(self) -> str:
        """Generate a unique 'Untitled-N' name for a new tab."""
        existing = {self._tabs.tabText(i) for i in range(self._tabs.count())}
        n = self._tabs.count() + 1
        while f"Untitled-{n}" in existing:
            n += 1
        return f"Untitled-{n}"

    def _on_tab_close_requested(self, index: int) -> None:
        self.close_tab(index)

    def _on_tab_changed(self, index: int) -> None:
        """Reassign ``self._canvas`` to the new active tab and rebind
        the docks + signal connections that depend on it."""
        if index < 0:
            return
        new_canvas = self._tabs.widget(index)
        if not isinstance(new_canvas, PaintCanvas):
            return
        # Disconnect signals from the old canvas and reconnect to the
        # new one so hover / zoom / document events route correctly.
        old_canvas = self._canvas
        if old_canvas is not None and old_canvas is not new_canvas:
            try:
                old_canvas.hover_changed.disconnect(self._on_hover_changed)
                old_canvas.image_loaded.disconnect(self._on_image_loaded)
                old_canvas.zoom_changed.disconnect(self._navigator_dock.set_zoom)
                old_canvas.document_changed.disconnect(self._on_document_changed)
            except (RuntimeError, TypeError):
                # Signal might already be disconnected (e.g. on shutdown).
                pass
        self._canvas = new_canvas
        self._canvas.set_tool_dispatcher(self._dispatcher)
        self._canvas.hover_changed.connect(self._on_hover_changed)
        self._canvas.image_loaded.connect(self._on_image_loaded)
        self._canvas.zoom_changed.connect(self._navigator_dock.set_zoom)
        self._canvas.document_changed.connect(self._on_document_changed)
        # Docks bound to the previous document need to point at the new one.
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(self._canvas.document())
        if hasattr(self, "_navigator_dock"):
            self._navigator_dock.set_zoom(self._canvas.zoom_factor())
        self._refresh_navigator_preview()

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

    # ---- window menu ----------------------------------------------------

    def _populate_window_menu(self) -> None:
        """One checkable Window-menu entry per dock — toggles visibility.

        Each entry's check state mirrors the dock's
        :meth:`isVisible` so closing a dock via its corner X also
        unchecks the menu item.
        """
        from Imervue.paint.paint_menu_bar import menu_for
        lang = language_wrapper.language_word_dict
        menu = menu_for(self, "window")
        entries = (
            ("paint_dock_color", "Color", self._color_dock),
            ("paint_dock_brush", "Brush", self._brush_dock),
            ("paint_dock_layers", "Layers", self._layer_dock),
            ("paint_dock_navigator", "Navigator", self._navigator_dock),
            ("paint_dock_material", "Materials", self._material_dock),
            ("paint_dock_history", "History", self._history_dock),
            ("paint_dock_swatches", "Swatches", self._swatch_dock),
            ("paint_dock_reference", "Reference", self._reference_dock),
            ("paint_dock_animation", "Animation", self._animation_dock),
            ("paint_dock_histogram", "Histogram", self._histogram_dock),
        )
        self._window_dock_actions = {}
        for key, fallback, dock in entries:
            action = menu.addAction(lang.get(key, fallback))
            action.setCheckable(True)
            action.setChecked(dock.isVisible() or True)
            action.triggered.connect(
                lambda checked, d=dock: d.setVisible(bool(checked)),
            )
            # Reflect external close (dock corner X).
            dock.visibilityChanged.connect(
                lambda visible, a=action: a.setChecked(bool(visible)),
            )
            self._window_dock_actions[key] = action
        # "New View" — spawn an independent overview window onto the
        # active document. Placed after the dock toggles so the
        # menu structure stays "all docks, then standalone windows".
        menu.addSeparator()
        new_view_action = menu.addAction(lang.get(
            "paint_window_new_view", "New View",
        ))
        new_view_action.triggered.connect(self.open_secondary_view)
        mirror_action = menu.addAction(lang.get(
            "paint_window_mirror_preview", "Mirror Preview",
        ))
        mirror_action.triggered.connect(self.open_mirror_preview)
        tile_action = menu.addAction(lang.get(
            "paint_window_tile_preview", "Tile Preview",
        ))
        tile_action.triggered.connect(self.open_tile_preview)

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
        """Drop a material onto the canvas based on its category.

        * ``pose`` — load full image, fit to canvas, paste into a new
          layer (existing behaviour).
        * ``texture`` / ``tone`` / ``pattern`` — render the tile,
          ``np.tile`` it across the canvas, and paste into a new
          layer named after the material.
        * ``brush_tip`` — placeholder (wired in a later phase).
        """
        from pathlib import Path

        from Imervue.paint.material_library import MaterialEntry

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
        if entry.category == "pose":
            self._drop_pose_material(entry)
        elif entry.category in ("texture", "tone", "pattern"):
            self._drop_tile_material(entry)
        elif entry.category == "brush_tip":
            self._drop_brush_tip_material(entry)

    def _drop_brush_tip_material(self, entry) -> None:
        """Bind the picked tip's PNG path to the active brush.

        Procedural ``brush_tip`` entries that don't have an on-disk
        path are silently ignored — the brush engine reads tips from
        a file path, so a virtual entry has nothing to point at.
        """
        if entry.is_procedural():
            return
        path = str(entry.path)
        if not path or path.startswith("procedural://"):
            return
        self._state.set_brush(tip_path=path)

    def _drop_pose_material(self, entry) -> None:
        from Imervue.paint.pose_drop import fit_pose_to_canvas, load_pose_image
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

    def _drop_tile_material(self, entry) -> None:
        """Tile a procedural / on-disk material across the canvas as
        a fresh layer. Honours the active selection: if a selection
        exists, the tiled fill is masked to it so the user can drop
        a tone "into" a region they've already lassoed."""
        from Imervue.paint.material_procedural import tile_to_canvas
        canvas_doc = self._canvas.document()
        if canvas_doc.shape is None:
            return
        tile = self._load_material_tile(entry)
        if tile is None:
            return
        h, w = canvas_doc.shape
        filled = tile_to_canvas(tile, (h, w))
        selection = self._canvas.current_selection()
        layer = canvas_doc.add_layer(name=f"{entry.category.title()} · {entry.name}")
        if selection is None:
            np.copyto(layer.image, filled)
        else:
            # Apply the tile only inside the selection mask; the rest
            # of the layer stays fully transparent.
            layer.image[selection] = filled[selection]
        canvas_doc.invalidate_composite()
        self._canvas.update()

    @staticmethod
    def _load_material_tile(entry):
        """Return an HxWx4 RGBA tile for ``entry``, or ``None`` on failure.

        Procedural entries call their provider; path entries are
        decoded via PIL so they go through the same code path as
        pose drops (no PySide image-format quirks). Both paths
        validate the array shape before returning so the caller can
        treat ``None`` as "nothing to paste".
        """
        if entry.is_procedural():
            try:
                tile = entry.render()
            except (ValueError, RuntimeError):
                return None
        else:
            from PIL import Image
            try:
                with Image.open(entry.path) as img:
                    tile = np.array(img.convert("RGBA"))
            except (OSError, ValueError):
                return None
        if (
            tile is None
            or tile.ndim != 3
            or tile.shape[2] != 4
            or tile.dtype != np.uint8
        ):
            return None
        return tile

    def _on_document_changed(self) -> None:
        """Mark the navigator preview dirty and start the coalesce timer."""
        self._nav_dirty = True
        if not self._nav_timer.isActive():
            self._nav_timer.start()

    def _refresh_navigator_preview(self) -> None:
        """Build a QPixmap of the current composite and push it to the dock.

        Also refreshes the histogram dock from the same composite —
        both consumers piggyback on the same coalesce timer to avoid
        re-running per brush dab.
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
        # fast path. QImage with bytesPerLine on a numpy view is safe so
        # long as the buffer stays alive — keep a reference on self
        # until the next refresh.
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
