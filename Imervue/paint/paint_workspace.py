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

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas, cursor_for_tool
from Imervue.paint.dock_panels import (
    BrushDock,
    FillDock,
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


def _safe_set_checked(action, value: bool) -> None:
    """Best-effort ``QAction.setChecked`` that survives shiboken
    teardown.

    Dock-visibility signals stay connected during workspace
    ``deleteLater()``; the C++ QAction can be freed before the
    signal-disconnect propagates, leaving a queued slot that
    would otherwise abort the GC pass with
    ``RuntimeError: Internal C++ object already deleted``.
    """
    try:
        action.setChecked(bool(value))
    except RuntimeError:
        return


logger = logging.getLogger("Imervue.paint.workspace")


class PaintWorkspace(QMainWindow):
    """Assembles the Paint tab from the toolbar + canvas + dock pieces."""

    def __init__(self, state: ToolState | None = None, parent=None):
        super().__init__(parent)
        # Accept image / PSD drops on the workspace itself so users
        # can drag a file from the OS file manager into the canvas.
        self.setAcceptDrops(True)
        self._state = state if state is not None else ts.load_tool_state()
        # Seed the MediBang-style default brush preset pack on first
        # workspace launch. Idempotent: when the user already has at
        # least one brush sub-tool the seeder bails out, so existing
        # users keep their saved presets and tests that build their
        # own state are unaffected.
        from Imervue.paint.default_brush_presets import (
            seed_default_brush_presets,
        )
        seed_default_brush_presets(self._state)

        # The embedded main window has its own menu bar so File / Edit
        # / Layer / View / Tools / Filter / Settings / Window all live
        # together — :func:`build_paint_menu_bar` populates the Filter
        # menu and stashes the others on the workspace as
        # ``_<key>_menu`` for the 21b–21g sub-phases to fill.
        self._build_menu_bar()

        # Status bar shows the cursor's image-space coordinates while painting.
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._build_zoom_indicator()
        # Cached most-recent cursor position in image space so
        # ``_refresh_status_line`` can re-render after a tool / brush
        # / selection change without waiting for the next hover.
        self._last_hover: tuple[int, int] | None = None
        # Per-tab "modified since last save" flag, keyed by canvas
        # widget. Drives the ``" *"`` tab title suffix and the
        # close-prompt protection.
        self._tab_dirty: dict = {}
        # ``time.monotonic()`` value of the most recent successful
        # autosave snapshot, or ``None`` while the workspace has
        # never run an autosave. Drives the "Last autosaved Xs ago"
        # status segment so the user always knows whether their
        # work is captured.
        self._last_autosave_at: float | None = None
        # Toast manager for non-blocking feedback (save / restore /
        # plugin install / file errors) — same widget the main image
        # viewer uses, scoped to this workspace as the parent so the
        # toast positions itself at the bottom of the paint area.
        from Imervue.gui.toast import ToastManager
        self.toast = ToastManager(self)

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
        # Middle-click on the tab bar should close the clicked tab —
        # cheap power-user convenience that mirrors browsers / IDEs.
        self._tabs.tabBar().installEventFilter(self)
        self._install_new_tab_corner_button()
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
        self._fill_dock = FillDock(self._state, self)
        self._fill_dock.set_auto_fill_callback(self._auto_fill_closed_regions)
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

        # Comic-project page browser. The dock binds to
        # ``self._paint_project`` (None until File ▸ New Project), so
        # every action degrades gracefully when no project is loaded.
        # Selecting a page swaps the active canvas's document with
        # that page's document.
        from Imervue.paint.page_dock import PageDock
        self._page_dock = PageDock(self, parent=self)
        self._page_dock.page_selected.connect(self._on_page_selected)

        # Comic stamp library — speech balloons / shouts / panel
        # borders inserted as new raster layers on click.
        from Imervue.paint.stamp_dock import StampDock
        self._stamp_dock = StampDock(parent=self)
        self._stamp_dock.stamp_chosen.connect(self._on_stamp_chosen)

        # Pose reference — interactive 2D stick figure the user can
        # drag joints on; "Insert" stamps the skeleton into the
        # active canvas as a guides layer.
        from Imervue.paint.pose_dock import PoseDock
        self._pose_dock = PoseDock(parent=self)
        self._pose_dock.insert_requested.connect(self._on_pose_insert)

        # Tabify every right-side dock into THREE logical clusters
        # rather than one 14-tab pile. The original single-cluster
        # layout met the sizeHint constraint (only the tallest dock
        # drives the column's minimum) but left the user picking
        # through fourteen tabs to find anything. Splitting into
        # three workflow-oriented groups keeps the same vertical
        # budget while giving each cluster a small, scannable tab
        # row matching MediBang's "drawing tools / canvas data /
        # libraries" mental model.
        drawing_cluster = (
            self._color_dock,
            self._brush_dock,
            self._fill_dock,
            self._swatch_dock,
        )
        canvas_cluster = (
            self._layer_dock,
            self._navigator_dock,
            self._history_dock,
            self._page_dock,
            self._animation_dock,
            self._histogram_dock,
        )
        library_cluster = (
            self._material_dock,
            self._stamp_dock,
            self._pose_dock,
            self._reference_dock,
        )
        all_right_docks = drawing_cluster + canvas_cluster + library_cluster
        self._install_dock_clusters(
            (drawing_cluster, canvas_cluster, library_cluster),
        )

        # Cache the cluster mapping so tool→dock-raise can find the
        # right anchor without re-deriving the layout each time.
        self._dock_clusters = {
            "drawing": drawing_cluster,
            "canvas": canvas_cluster,
            "library": library_cluster,
        }

        # Stable objectName per dock so QMainWindow.saveState()/
        # restoreState() can match docks across launches. Without
        # this Qt has no reliable identifier (windowTitle is
        # locale-translated and changes), and restoreState silently
        # produces undefined results.
        dock_object_names = {
            id(self._color_dock): "paint_dock_color",
            id(self._brush_dock): "paint_dock_brush",
            id(self._fill_dock): "paint_dock_fill",
            id(self._layer_dock): "paint_dock_layers",
            id(self._navigator_dock): "paint_dock_navigator",
            id(self._material_dock): "paint_dock_material",
            id(self._history_dock): "paint_dock_history",
            id(self._swatch_dock): "paint_dock_swatches",
            id(self._reference_dock): "paint_dock_reference",
            id(self._animation_dock): "paint_dock_animation",
            id(self._page_dock): "paint_dock_pages",
            id(self._stamp_dock): "paint_dock_stamps",
            id(self._pose_dock): "paint_dock_pose",
            id(self._histogram_dock): "paint_dock_histogram",
        }
        for dock in all_right_docks:
            dock.setObjectName(dock_object_names[id(dock)])
            dock.setFeatures(
                dock.features()
                | dock.DockWidgetFeature.DockWidgetMovable
                | dock.DockWidgetFeature.DockWidgetFloatable,
            )

        # Window menu — toggle each dock's visibility from the
        # workspace's menu bar so the user can hide / show panels
        # without right-clicking the toolbar.
        self._populate_window_menu()

        # Restore the user's saved dock layout (which docks are
        # tabbed, which are floating, which are hidden, etc.) from
        # ``user_setting_dict``. Safe to call after the default
        # cluster layout above — ``restoreState`` overwrites the
        # default when a saved blob exists, otherwise falls through.
        self._restore_dock_state()

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
        # Zoom change → resize the brush-ring cursor so its on-screen
        # diameter keeps tracking size × zoom (Medibang-style preview).
        self._canvas.zoom_changed.connect(self._on_zoom_changed_refresh_cursor)
        # Right-click anywhere on the canvas → quick-actions menu.
        self._canvas.customContextMenuRequested.connect(
            self._show_canvas_context_menu,
        )

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
        # Per-document undo / redo stack — committed by the dispatcher
        # whenever a tool reports a successful mutation.
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
        # Shape tools (rect / ellipse / line / polygon) consume the
        # workspace handle so View → Snap to Edges can pull the start
        # / end vertices to canvas + layer edges. Without the
        # workspace they silently disable the snap and use raw
        # pointer coordinates — matches the lazy-attach pattern used
        # by the bezier pen.
        for shape_key in ("shape_rect", "shape_ellipse", "shape_line", "shape_polygon"):
            shape_tool = self._dispatcher._handlers.get(shape_key)  # noqa: SLF001
            if (
                shape_tool is not None
                and hasattr(shape_tool, "attach_workspace")
            ):
                shape_tool.attach_workspace(self)

        self._unsubscribe = self._state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._refresh_cursor_for_tool()

        # Now safe to wire tab-change re-binding — every dock and the
        # dispatcher have been constructed above.
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Welcome hint — translucent panel that overlays a fresh,
        # untouched canvas with drag-drop affordance + new / open /
        # recent shortcuts. Shown until the first real edit, then
        # dismissed for the rest of the workspace lifetime.
        self._build_welcome_hint()
        # Surface any autosave snapshots left behind by a previous
        # crash before the user starts a fresh stroke. The prompt
        # suppresses itself on a clean launch so the boot path stays
        # silent in the common case.
        self._maybe_offer_autosave_recovery()
        # Brush-kind cycle shortcuts — Comma cycles backwards,
        # Period forwards. Mirrors the Photoshop convention so users
        # coming from PS land with familiar keys.
        self._build_brush_kind_shortcuts()

    # ---- public ----------------------------------------------------------

    def canvas(self) -> PaintCanvas:
        return self._canvas

    def state(self) -> ToolState:
        return self._state

    # ---- dock layout persistence ---------------------------------------

    DOCK_STATE_SETTING_KEY = "paint_workspace_dock_state"

    def _save_dock_state(self) -> None:
        """Serialise the current dock layout into ``user_setting_dict``.

        ``QMainWindow.saveState`` returns a QByteArray that captures
        which docks are tabbed together, which are floating, where
        they sit, and their visibility. We base64-encode it so the
        JSON-serialised settings file can carry the binary blob.
        """
        from base64 import b64encode

        from Imervue.user_settings.user_setting_dict import user_setting_dict

        blob = bytes(self.saveState().data())
        user_setting_dict[self.DOCK_STATE_SETTING_KEY] = b64encode(blob).decode("ascii")

    def _restore_dock_state(self) -> None:
        """Apply the saved dock layout from ``user_setting_dict``.

        Returns silently when no saved layout exists (first run) or
        when ``restoreState`` rejects the blob (after a dock was
        added / removed in a newer build, the saved state references
        unknown objects and Qt skips it). Either way the default
        cluster layout configured in ``__init__`` stays in place.

        Wrapped in try/except so a corrupt blob never crashes the
        workspace constructor — broken state is the user's local
        settings file, not a bug to surface to a fresh launch.
        """
        from base64 import b64decode

        from Imervue.user_settings.user_setting_dict import user_setting_dict

        encoded = user_setting_dict.get(self.DOCK_STATE_SETTING_KEY)
        if not encoded:
            return
        try:
            blob = b64decode(encoded)
        except (ValueError, TypeError):
            return
        try:
            from PySide6.QtCore import QByteArray
            self.restoreState(QByteArray(blob))
        except (RuntimeError, ValueError, TypeError):
            return

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

    def _has_unsaved_tabs(self) -> bool:
        """Return True if any of the open tabs has the dirty flag set.

        Iterates over the live ``_tab_dirty`` map rather than the
        QTabWidget so a stale entry that was never cleaned up doesn't
        accidentally claim an unsaved tab. Closed tabs are popped from
        the map at close time, so anything in here is real.
        """
        return any(self._tab_dirty.get(w, False) for w in self._tab_dirty)

    def _unsaved_tab_titles(self) -> list[str]:
        """Return the titles of every tab carrying unsaved edits.

        Pulled out of the close prompt so a future "save all" command
        can surface the same list without re-walking the dirty map.
        """
        names: list[str] = []
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if not self._tab_dirty.get(widget, False):
                continue
            names.append(self._tabs.tabText(i).rstrip(" *"))
        return names

    def _confirm_discard_all_unsaved(self) -> bool:
        """Prompt the user before tearing down a window with dirty tabs.

        Returns ``True`` for "Discard all" or "Save…"-then-clean,
        ``False`` for cancel. Lists the titles inline so the user
        can see exactly which tabs are about to be lost.
        """
        from PySide6.QtWidgets import QMessageBox
        lang = language_wrapper.language_word_dict
        names = self._unsaved_tab_titles()
        title = lang.get(
            "paint_close_window_unsaved_title",
            "Close with unsaved changes?",
        )
        body_template = lang.get(
            "paint_close_window_unsaved_body",
            "{count} tab(s) with unsaved edits:\n• {names}",
        )
        body = body_template.format(
            count=len(names), names="\n• ".join(names),
        )
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(body)
        box.setIcon(QMessageBox.Icon.Warning)
        save = box.addButton(
            lang.get("paint_close_window_save_active", "Save active…"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard = box.addButton(
            lang.get("paint_close_window_discard_all", "Discard all"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "export_active_image"):
                bridge.export_active_image()
            # If export marked the active tab clean and that was the
            # only dirty one, allow the close. Otherwise the user has
            # to invoke close again — the message box doesn't loop.
            return not self._has_unsaved_tabs()
        return clicked is discard

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

        PSDs route through the file-menu bridge so the open feeds
        the recent-files list. Plain raster files are loaded into
        the active canvas via load_image — same path as the existing
        File ▸ Open flow for non-PSDs.
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
            import numpy as np
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

    def toggle_all_docks(self) -> bool:
        """Hide every right-side dock for distraction-free painting,
        or restore them when called again.

        Industry-standard "Tab" key behaviour — Photoshop / Krita /
        MediBang all bind it. Returns the new visibility state so
        callers can update menu check-marks if needed.

        State is tracked per-call via :attr:`_docks_collapsed` so
        the second invocation restores the exact set of docks that
        were visible before; a dock the user had already hidden via
        its corner X stays hidden after the un-toggle, matching the
        Photoshop convention.
        """
        clusters = getattr(self, "_dock_clusters", None)
        if not clusters:
            return False
        all_docks = (
            clusters.get("drawing", ()) + clusters.get("canvas", ())
            + clusters.get("library", ())
        )
        collapsed = getattr(self, "_docks_collapsed", None)
        if collapsed is None:
            # Capture the current visibility set, then hide everything
            # the user hadn't already manually hidden. ``isHidden`` is
            # the local "explicitly setVisible(False)" flag — independent
            # of parent visibility, which matters because the workspace
            # may not be shown yet (tests, deferred boot).
            self._docks_collapsed = {
                dock: (not dock.isHidden()) for dock in all_docks
            }
            for dock in all_docks:
                if not dock.isHidden():
                    dock.setVisible(False)
            return False
        # Restore exactly the set that was visible at collapse time.
        for dock, was_visible in collapsed.items():
            dock.setVisible(was_visible)
        self._docks_collapsed = None
        return True

    def reset_workspace_layout(self) -> None:
        """Re-apply the default three-cluster layout.

        Drops any saved state (so the next launch also starts on
        the default), removes every right-side dock from its
        current home, then re-tabifies the three clusters in their
        canonical order. Useful when the user has shuffled docks
        into corners or floated everything and wants a clean slate.
        """
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        user_setting_dict.pop(self.DOCK_STATE_SETTING_KEY, None)
        clusters = getattr(self, "_dock_clusters", None)
        if not clusters:
            return
        ordered = (
            clusters.get("drawing", ()) + clusters.get("canvas", ())
            + clusters.get("library", ())
        )
        # Remove every dock from the main window first; addDockWidget
        # then puts each into the right area and tabifyDockWidget
        # pairs them. Without the explicit remove pass docks that
        # the user floated stay floated through the reset.
        for dock in ordered:
            self.removeDockWidget(dock)
        for cluster_name in ("drawing", "canvas", "library"):
            cluster = clusters.get(cluster_name, ())
            if not cluster:
                continue
            anchor = cluster[0]
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, anchor)
            anchor.show()
            for dock in cluster[1:]:
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
                self.tabifyDockWidget(anchor, dock)
                dock.show()
            anchor.raise_()

    # ---- secondary views -----------------------------------------------

    def _on_dispatcher_commit(self) -> None:
        """Push an undo snapshot after the dispatcher commits a stroke.

        Called by the dispatcher only at gesture boundaries (release
        for brushes, single-click commits for fill / wand / shape) so
        a long brush stroke counts as one undoable action rather than
        every dab. The actual capture happens inside the UndoStack.
        Also flips the active tab to "modified" so the title shows
        an asterisk and the close handler knows to prompt before
        discarding unsaved work.
        """
        self._undo_stack.commit()
        self._set_tab_dirty(self._canvas, True)

    def undo(self) -> None:
        """Undo the most recent committed stroke if there is one.

        Pops a non-blocking toast on success so keyboard users
        (Ctrl+Z) get a visible confirmation that the action landed,
        and surfaces a "nothing to undo" hint when the stack is
        already at the bottom — otherwise repeated Ctrl+Z taps with
        no audible / visible feedback feel like the binding is broken.
        """
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

        Falls back to the status bar's transient message when the
        toast isn't wired (legacy embedders / minimal test stubs).
        Both paths surface the action *and* the remaining depth so
        the user can pace their Ctrl+Z taps without overshooting.
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
        :class:`UndoStack` doesn't expose the queried side (older
        embedders or future refactors).
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
        from Imervue.paint.auto_save import DEFAULT_INTERVAL_SEC
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
        """Force an immediate document snapshot.

        Writes the full :class:`PaintDocument` (layers, masks, vectors,
        animation) through :mod:`auto_save` so a crash restore brings
        back the project — not just a flat composite. Returns the
        bundle path or ``None`` if there is nothing to save (empty
        document) or the write failed. On success records the wall-
        clock timestamp so the status line can render
        "Last autosaved Xs ago" — that hint is what tells the user
        their work is captured even when no file has been picked.
        """
        import time
        from Imervue.paint.auto_save import write_snapshot
        document = self._canvas.document()
        target = getattr(self, "_autosave_target_dir", None)
        try:
            snapshot = write_snapshot(document, directory=target)
        except (OSError, ValueError):
            return None
        if snapshot is None:
            return None
        self._last_autosave_at = time.monotonic()
        self._refresh_status_line()
        return snapshot.bundle_path

    def pending_autosaves(self, *, target_dir=None):
        """Return non-stale recovery candidates for ``target_dir``.

        Thin pass-through over :func:`auto_save.pending_recovery_snapshots`
        so the recovery prompt UI can call into the workspace without
        importing the autosave module directly.
        """
        from Imervue.paint.auto_save import pending_recovery_snapshots
        return pending_recovery_snapshots(target_dir)

    def restore_snapshot(self, snapshot) -> bool:
        """Install ``snapshot``'s document on the canvas.

        Uses :meth:`PaintCanvas.set_document` so layers, masks, vector
        layers, and selections all survive the restore. Returns
        ``False`` when the bundle is unreadable; ``True`` on success.
        """
        from Imervue.paint.auto_save import recover_snapshot
        try:
            document = recover_snapshot(snapshot)
        except (OSError, ValueError):
            return False
        self._canvas.set_document(document)
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(document)
        return True

    def restore_latest_autosave(self, *, target_dir=None) -> bool:
        """Load the most-recent recovery snapshot onto the canvas.

        Returns ``True`` when a snapshot was found and installed; the
        caller drives the user-visible "restore?" prompt around this.
        """
        snapshots = self.pending_autosaves(target_dir=target_dir)
        if not snapshots:
            return False
        return self.restore_snapshot(snapshots[0])

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

    # ---- pose reference --------------------------------------------------

    def _on_pose_insert(self, skeleton) -> None:
        """User clicked "Insert" on the pose dock. Render the
        skeleton into a fresh layer at canvas size."""
        from Imervue.paint.pose_skeleton import render_skeleton

        document = self._canvas.document()
        shape = document.shape
        if shape is None:
            return
        h, w = shape
        rendered = render_skeleton(skeleton, height=h, width=w)
        layer = document.add_layer(name="Pose")
        np.copyto(layer.image, rendered)
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()

    # ---- stamp library ---------------------------------------------------

    def _on_stamp_chosen(self, key: str) -> None:
        """User clicked a stamp thumbnail. Render it at ~1/3 of the
        canvas size and paste it into a new layer at canvas centre."""
        from Imervue.paint.comic_stamps import render_stamp

        document = self._canvas.document()
        shape = document.shape
        if shape is None:
            return
        h, w = shape
        target_w = max(64, int(w * 0.35))
        target_h = max(64, int(h * 0.30))
        stamp = render_stamp(key, target_w, target_h)
        sh, sw = stamp.shape[:2]
        # Add a transparent layer at the document's size, then paint
        # the stamp into its centre. Going through ``add_layer`` keeps
        # the document's invariants (active-index update, reference
        # shift, listener notify) intact.
        layer = document.add_layer(name=key)
        x0 = max(0, (w - sw) // 2)
        y0 = max(0, (h - sh) // 2)
        x1 = min(w, x0 + sw)
        y1 = min(h, y0 + sh)
        layer.image[y0:y1, x0:x1] = stamp[: y1 - y0, : x1 - x0]
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()

    # ---- auto-region fill ------------------------------------------------

    def _auto_fill_closed_regions(self) -> None:
        """Paint the foreground colour into every enclosed region of
        the document's reference layer (or the active layer when no
        reference layer is set). Pushes one undo entry on success."""
        from Imervue.paint.auto_region_fill import auto_region_fill

        document = self._canvas.document()
        target = document.active_layer()
        if target is None:
            return
        ref_idx = document.reference_layer_index()
        line_art = (
            target.image if ref_idx is None
            else document.layer_at(ref_idx).image
        )
        if self._state.foreground is None:
            return
        result = auto_region_fill(
            target.image,
            line_art,
            self._state.foreground,
        )
        if result.is_empty:
            return
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()

    # ---- comic-project page browser --------------------------------------

    def set_paint_project(self, project) -> None:
        """Bind ``project`` (a :class:`PaintProject` or ``None``) to the
        workspace and refresh the page dock. The dock degrades to its
        empty state when ``project`` is ``None``."""
        self._paint_project = project
        page_dock = getattr(self, "_page_dock", None)
        if page_dock is not None:
            page_dock.refresh()
        # If a project just bound, swap the active canvas to the
        # project's active page so the user sees the right document
        # immediately.
        if project is not None and project.active_page() is not None:
            self._swap_canvas_document(project.active_page().document)

    def _on_page_selected(self, index: int) -> None:
        """Page-list click — swap the active canvas's document with
        the selected page's document. The canvas keeps its tab name
        but shows the new document; ``current_image()`` and the layer
        dock auto-refresh because the dock subscribes to the new
        document's listeners."""
        project = getattr(self, "_paint_project", None)
        if project is None:
            return
        try:
            page = project.page_at(index)
        except IndexError:
            return
        self._swap_canvas_document(page.document)

    def _swap_canvas_document(self, document) -> None:
        """Replace the active canvas's PaintDocument with ``document``.

        Re-binds the layer dock + the dispatcher's image / selection
        providers so they read from the new document. The canvas's
        own ``_document`` reference is updated through the public
        ``set_document`` setter.
        """
        if not hasattr(self._canvas, "set_document"):
            return
        self._canvas.set_document(document)
        if hasattr(self._layer_dock, "set_document"):
            self._layer_dock.set_document(document)
        self._canvas.update()

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

    def close_tab(self, index: int, *, force: bool = False) -> bool:
        """Close the tab at ``index``. Returns ``True`` on success.

        Refuses to close the last remaining tab — the workspace
        always needs at least one paintable canvas, mirroring the
        single-tab invariant from before tabs existed. ``force=True``
        bypasses the unsaved-work prompt; the tabCloseRequested
        handler uses it after the user explicitly confirms discard.
        """
        if index < 0 or index >= self._tabs.count():
            return False
        if self._tabs.count() <= 1:
            return False
        widget = self._tabs.widget(index)
        needs_prompt = (
            not force and self._tab_dirty.get(widget, False)
        )
        if needs_prompt and not self._confirm_discard_unsaved(widget):
            return False
        self._tab_dirty.pop(widget, None)
        self._tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        return True

    def _confirm_discard_unsaved(self, widget) -> bool:
        """Prompt the user before closing a tab with unsaved edits.

        Returns ``True`` when the user picks "Discard"; ``False``
        when they cancel. ``Save`` is offered as a third option that
        triggers the active export and re-checks the dirty flag.
        """
        from PySide6.QtWidgets import QMessageBox
        lang = language_wrapper.language_word_dict
        title = lang.get(
            "paint_close_unsaved_title", "Close tab with unsaved changes?",
        )
        body = lang.get(
            "paint_close_unsaved_body",
            "This tab has unsaved edits. Close anyway?",
        )
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(body)
        box.setIcon(QMessageBox.Icon.Question)
        save = box.addButton(
            lang.get("paint_close_unsaved_save", "Save…"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard = box.addButton(
            lang.get("paint_close_unsaved_discard", "Discard"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "export_active_image"):
                bridge.export_active_image()
            # If the export marked clean, the next discard branch
            # below would happily proceed; otherwise the user can
            # invoke close again with the new state.
            return not self._tab_dirty.get(widget, False)
        return clicked is discard

    def _next_untitled_tab_name(self) -> str:
        """Generate a unique 'Untitled-N' name for a new tab."""
        existing = {
            self._tabs.tabText(i).rstrip(" *")
            for i in range(self._tabs.count())
        }
        n = self._tabs.count() + 1
        while f"Untitled-{n}" in existing:
            n += 1
        return f"Untitled-{n}"

    def _on_tab_close_requested(self, index: int) -> None:
        self.close_tab(index)

    # ---- per-tab dirty tracking ------------------------------------------

    def _set_tab_dirty(self, canvas, dirty: bool) -> None:
        """Update the per-tab modified flag + tab title.

        Tab titles end with a trailing ``" *"`` while dirty so the
        user sees at a glance which tabs carry unsaved edits. The
        flag map is keyed by the canvas widget itself so closing a
        tab cleans up the entry without leaking references.
        """
        if canvas is None:
            return
        prev = self._tab_dirty.get(canvas, False)
        if prev == dirty:
            return
        self._tab_dirty[canvas] = dirty
        self._refresh_tab_title(canvas)

    def _refresh_tab_title(self, canvas) -> None:
        index = self._tabs.indexOf(canvas)
        if index < 0:
            return
        base = self._tabs.tabText(index).rstrip(" *")
        suffix = " *" if self._tab_dirty.get(canvas, False) else ""
        self._tabs.setTabText(index, f"{base}{suffix}")
        self._refresh_tab_tooltip(canvas, base)

    def _refresh_tab_tooltip(self, canvas, base_title: str) -> None:
        """Populate the per-tab hover tooltip with the full title +
        canvas dimensions + dirty state.

        Tab text gets truncated by Qt when the bar is full; the
        tooltip is the only place we can guarantee the full label
        is reachable. We also surface size / modified state so a
        user with several tabs can compare at a glance which one
        is the WIP.
        """
        index = self._tabs.indexOf(canvas)
        if index < 0:
            return
        lang = language_wrapper.language_word_dict
        lines: list[str] = [base_title]
        document = (
            canvas.document() if hasattr(canvas, "document") else None
        )
        shape = getattr(document, "shape", None) if document is not None else None
        if shape is not None:
            h, w = shape
            lines.append(
                lang.get("paint_tab_tooltip_size", "{w}×{h}").format(w=w, h=h),
            )
        if self._tab_dirty.get(canvas, False):
            lines.append(
                lang.get("paint_tab_tooltip_modified", "Modified — unsaved"),
            )
        self._tabs.setTabToolTip(index, "\n".join(lines))

    def mark_active_tab_clean(self) -> None:
        """Public hook called by file-menu save / export actions."""
        self._set_tab_dirty(self._canvas, False)

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
                old_canvas.zoom_changed.disconnect(self._on_zoom_changed_refresh_cursor)
                old_canvas.document_changed.disconnect(self._on_document_changed)
            except (RuntimeError, TypeError):
                # Signal might already be disconnected (e.g. on shutdown).
                pass
        self._canvas = new_canvas
        self._canvas.set_tool_dispatcher(self._dispatcher)
        self._canvas.hover_changed.connect(self._on_hover_changed)
        self._canvas.image_loaded.connect(self._on_image_loaded)
        self._canvas.zoom_changed.connect(self._navigator_dock.set_zoom)
        self._canvas.zoom_changed.connect(self._on_zoom_changed_refresh_cursor)
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
        """Checkable dock toggles grouped into three cluster submenus.

        Window menu structure:
          ▸ Drawing       (Color / Brush / Bucket / Swatches)
          ▸ Canvas        (Layer / Navigator / History / Pages / …)
          ▸ Library       (Material / Stamps / Pose / Reference)
          ─────
          New View / Mirror Preview / Tile Preview
          ─────
          Reset Workspace Layout

        Each toggle's check state mirrors the dock's ``isVisible``
        so closing a dock via its corner X also unchecks the entry.
        """
        from Imervue.paint.paint_menu_bar import menu_for
        lang = language_wrapper.language_word_dict
        menu = menu_for(self, "window")
        cluster_entries = {
            "drawing": (
                ("paint_dock_color", "Color", self._color_dock),
                ("paint_dock_brush", "Brush", self._brush_dock),
                ("paint_dock_fill", "Bucket", self._fill_dock),
                ("paint_dock_swatches", "Swatches", self._swatch_dock),
            ),
            "canvas": (
                ("paint_dock_layers", "Layers", self._layer_dock),
                ("paint_dock_navigator", "Navigator", self._navigator_dock),
                ("paint_dock_history", "History", self._history_dock),
                ("paint_dock_pages", "Pages", self._page_dock),
                ("paint_dock_animation", "Animation", self._animation_dock),
                ("paint_dock_histogram", "Histogram", self._histogram_dock),
            ),
            "library": (
                ("paint_dock_material", "Materials", self._material_dock),
                ("paint_dock_stamps", "Stamps", self._stamp_dock),
                ("paint_dock_pose", "Pose", self._pose_dock),
                ("paint_dock_reference", "Reference", self._reference_dock),
            ),
        }
        cluster_titles = {
            "drawing": ("paint_window_group_drawing", "Drawing"),
            "canvas": ("paint_window_group_canvas", "Canvas"),
            "library": ("paint_window_group_library", "Library"),
        }
        self._window_dock_actions = {}
        for cluster_key in ("drawing", "canvas", "library"):
            title_key, title_fallback = cluster_titles[cluster_key]
            submenu = menu.addMenu(lang.get(title_key, title_fallback))
            for key, fallback, dock in cluster_entries[cluster_key]:
                action = submenu.addAction(lang.get(key, fallback))
                action.setCheckable(True)
                action.setChecked(dock.isVisible() or True)
                action.triggered.connect(
                    lambda checked, d=dock: d.setVisible(bool(checked)),
                )
                # Reflect external close (dock corner X). Wrap the
                # ``setChecked`` call so a teardown that frees the
                # QAction's C++ side before the dock's signal fully
                # disconnects doesn't leave a dangling
                # RuntimeError-raising slot in the queue.
                dock.visibilityChanged.connect(
                    lambda visible, a=action: _safe_set_checked(a, visible),
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
        # Reset Layout — escape hatch for a user who shuffled docks
        # off-screen or floated everything. Drops the saved state
        # blob from user_setting_dict and re-applies the canonical
        # cluster layout the constructor uses on a fresh install.
        menu.addSeparator()
        reset_action = menu.addAction(lang.get(
            "paint_window_reset_layout", "Reset Workspace Layout",
        ))
        reset_action.triggered.connect(self.reset_workspace_layout)

    # ---- handlers --------------------------------------------------------

    # Tools whose cursor is the Medibang-style brush ring (diameter
    # tracks size × zoom). All five paint with ``state.brush.size``
    # so the ring is a meaningful preview for every one of them;
    # other tools (eyedropper, fill, gradient, …) get tool-specific
    # icons via :func:`make_tool_cursor`.
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
        """Connect-target for ``canvas.zoom_changed`` — re-draws the
        brush ring at the new screen-pixel diameter when the active
        tool uses it, and updates the status-bar zoom indicator so
        the chip stays in sync with whatever wheel / pinch / View
        menu action just landed."""
        if self._state.tool in self._BRUSH_RING_TOOLS:
            self._refresh_cursor_for_tool()
        self._refresh_zoom_indicator(zoom)

    # Tool ID → dock to raise so the relevant settings panel pops to
    # the front of its tab cluster. Tools whose options live in a
    # dock not in this map (selection, transform, hand, zoom) leave
    # the current tab untouched.
    _TOOL_DOCK_MAP_ATTR = "_TOOL_DOCK_MAP"

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
        # raise_() is a no-op for a non-tabbed (top-level) dock, so
        # safe to call regardless of whether the cluster is currently
        # tabified or split apart by a custom user layout.
        dock.raise_()

    def _on_hover_changed(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            self._last_hover = None
        else:
            self._last_hover = (int(x), int(y))
        self._refresh_status_line()

    def _show_canvas_context_menu(self, pos) -> None:
        """Pop a Photoshop-style quick-actions menu at the right-click
        position on the canvas. Construction is delegated to
        :meth:`_build_canvas_context_menu` so unit tests can verify
        the action set without driving Qt's modal loop."""
        menu = self._build_canvas_context_menu()
        menu.exec(self._canvas.mapToGlobal(pos))

    def _build_canvas_context_menu(self):
        """Return the QMenu that ``_show_canvas_context_menu`` pops.

        Surfaces the actions users hit most often via the keyboard
        (undo / redo / select all / deselect / fit / 100 %) so they
        can be reached without a trip to the menu bar. Each entry is
        wired to the same workspace methods the menu / shortcut
        invokes — there's no duplicate dispatcher path.
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

    def _install_new_tab_corner_button(self) -> None:
        """Mount a small "+" button in the tab strip's right corner so
        the artist has a one-click affordance for ``new_tab`` without
        memorising Ctrl+T or hunting in the File menu."""
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

    def _install_dock_clusters(self, clusters: tuple) -> None:
        """Anchor each cluster's first dock on the right edge and tabify
        the rest behind it. Pulled out of ``__init__`` so the constructor
        stays under the cognitive-complexity budget."""
        for cluster in clusters:
            anchor = cluster[0]
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, anchor)
            for dock in cluster[1:]:
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
                self.tabifyDockWidget(anchor, dock)
            anchor.raise_()

    def _build_menu_bar(self) -> None:
        """Construct the embedded menu bar and populate every section.

        Extracted from ``__init__`` so the constructor stays under the
        cognitive-complexity budget; ordering matches the original
        File → Edit → Image → Layer → View → Tools → Manga → Settings
        layout the artists are used to.
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

    def _build_zoom_indicator(self) -> None:
        """Add a clickable zoom % chip to the right side of the status bar.

        Click toggles between "Fit to window" (when current zoom is
        close to 1.0) and 100 % zoom (when it's anything else) so
        the user has a one-click view-reset path that doesn't
        require the View menu.
        """
        from PySide6.QtWidgets import QToolButton
        lang = language_wrapper.language_word_dict
        self._zoom_btn = QToolButton(self)
        self._zoom_btn.setAutoRaise(True)
        self._zoom_btn.setText(
            lang.get("paint_status_zoom_initial", "100%"),
        )
        self._zoom_btn.setToolTip(lang.get(
            "paint_status_zoom_tooltip",
            "Click to toggle between Fit to window and 100 %",
        ))
        self._zoom_btn.clicked.connect(self._on_zoom_indicator_clicked)
        self._status.addPermanentWidget(self._zoom_btn)

    def _refresh_zoom_indicator(self, zoom: float | None = None) -> None:
        if not hasattr(self, "_zoom_btn"):
            return
        if zoom is None:
            canvas = getattr(self, "_canvas", None)
            zoom = canvas.zoom_factor() if canvas is not None else 1.0
        self._zoom_btn.setText(f"{int(round(float(zoom) * 100))}%")

    def _on_zoom_indicator_clicked(self) -> None:
        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            return
        if abs(canvas.zoom_factor() - 1.0) < 0.01:
            canvas.reset_view()
        else:
            canvas.set_zoom(1.0)

    def _build_brush_kind_shortcuts(self) -> None:
        """Bind ``,`` / ``.`` to cycle the active brush kind, the
        digit row to set opacity in Photoshop's 10 % grid, and
        ``Alt+[`` / ``Alt+]`` to step the active layer down / up."""
        from PySide6.QtGui import QKeySequence, QShortcut
        prev_shortcut = QShortcut(QKeySequence(","), self)
        prev_shortcut.activated.connect(lambda: self.cycle_brush_kind(-1))
        next_shortcut = QShortcut(QKeySequence("."), self)
        next_shortcut.activated.connect(lambda: self.cycle_brush_kind(+1))
        for digit in range(10):
            shortcut = QShortcut(QKeySequence(str(digit)), self)
            shortcut.activated.connect(
                lambda d=digit: self.set_brush_opacity_from_digit(d),
            )
        layer_down = QShortcut(QKeySequence("Alt+["), self)
        layer_down.activated.connect(lambda: self.cycle_active_layer(-1))
        layer_up = QShortcut(QKeySequence("Alt+]"), self)
        layer_up.activated.connect(lambda: self.cycle_active_layer(+1))
        # Brush size step — Photoshop / MediBang convention. Bracket
        # keys without a modifier so the artist can keep one hand on
        # the canvas. Step amount is multiplicative when held with
        # Shift so artists can resize quickly across orders of magnitude.
        size_dec = QShortcut(QKeySequence("["), self)
        size_dec.activated.connect(lambda: self.step_brush_size(-1))
        size_inc = QShortcut(QKeySequence("]"), self)
        size_inc.activated.connect(lambda: self.step_brush_size(+1))
        size_big_dec = QShortcut(QKeySequence("Shift+["), self)
        size_big_dec.activated.connect(lambda: self.step_brush_size(-5))
        size_big_inc = QShortcut(QKeySequence("Shift+]"), self)
        size_big_inc.activated.connect(lambda: self.step_brush_size(+5))
        # Tab navigation — Ctrl+Tab cycles forward, Ctrl+Shift+Tab
        # backward. Standard browser / IDE convention so users with
        # several open documents don't need to reach for the mouse.
        next_tab = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab.activated.connect(lambda: self.cycle_active_tab(+1))
        prev_tab = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab.activated.connect(lambda: self.cycle_active_tab(-1))

    BRUSH_SIZE_MIN = 1
    BRUSH_SIZE_MAX = 500

    def step_brush_size(self, delta: int) -> int:
        """Adjust the brush size by ``delta`` pixels and clamp to the
        documented range. Returns the new size so tests + the status
        bar can read back without re-querying state.
        """
        state = getattr(self, "_state", None)
        if state is None:
            return 0
        current = int(state.brush.size)
        new_size = max(self.BRUSH_SIZE_MIN, min(self.BRUSH_SIZE_MAX, current + int(delta)))
        if new_size != current:
            state.set_brush(size=new_size)
            self._refresh_status_line()
        return new_size

    def cycle_active_tab(self, direction: int) -> int:
        """Step the active paint tab by ``direction`` (+1 / -1).

        Wraps around at both ends — the workspace has a small,
        bounded set of tabs and wrapping is the friendlier behaviour
        when keyboard-cycling.
        """
        count = self._tabs.count()
        if count <= 1:
            return self._tabs.currentIndex()
        new_index = (self._tabs.currentIndex() + int(direction)) % count
        self._tabs.setCurrentIndex(new_index)
        return new_index

    def cycle_active_layer(self, direction: int) -> int | None:
        """Step the document's active layer index by ``direction``.

        Returns the new index (clamped, never wraps — wrapping at
        the bottom would loop the user back to the top layer with
        no warning, which is jarring) or ``None`` if no document is
        loaded. Toasts the new layer's name so the user has a
        visible signal that the keystroke registered.
        """
        document = self._canvas.document() if self._canvas else None
        if document is None or not hasattr(document, "set_active_layer"):
            return None
        count = getattr(document, "layer_count", 0)
        if count <= 0:
            return None
        current = document.active_layer_index()
        new_idx = max(0, min(count - 1, current + int(direction)))
        if new_idx == current:
            return current
        document.set_active_layer(new_idx)
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(document)
        layer = (
            document.active_layer()
            if hasattr(document, "active_layer") else None
        )
        if layer is not None:
            lang = language_wrapper.language_word_dict
            toast = getattr(self, "toast", None)
            if toast is not None:
                toast.info(
                    lang.get(
                        "paint_layer_active_changed", "Layer: {name}",
                    ).format(name=str(getattr(layer, "name", ""))),
                    duration_ms=1500,
                )
        self._refresh_status_line()
        return new_idx

    def set_brush_opacity_from_digit(self, digit: int) -> float:
        """Map a 0-9 keystroke to a brush opacity value.

        Photoshop convention — ``1`` → 10 %, ``2`` → 20 %, …, ``9``
        → 90 %, ``0`` → 100 %. Returns the resulting opacity in
        ``[0, 1]`` so callers / tests can verify the mapping.
        """
        digit = int(digit) % 10
        opacity = 1.0 if digit == 0 else digit / 10.0
        self._state.set_brush(opacity=opacity)
        lang = language_wrapper.language_word_dict
        msg = lang.get(
            "paint_brush_opacity_changed", "Opacity: {pct}%",
        ).format(pct=int(round(opacity * 100)))
        toast = getattr(self, "toast", None)
        if toast is not None:
            toast.info(msg, duration_ms=1200)
        return opacity

    def cycle_brush_kind(self, direction: int) -> str:
        """Cycle the brush kind by ``direction`` (+1 forward, -1 back).

        Returns the resulting kind so callers / tests can verify the
        cycle landed on the expected entry. Toasts a confirmation
        with the new kind's display name so the user has a visible
        signal that the keystroke registered.
        """
        kinds = list(ts.BRUSH_KINDS)
        try:
            idx = kinds.index(self._state.brush.kind)
        except ValueError:
            idx = 0
        new_idx = (idx + int(direction)) % len(kinds)
        new_kind = kinds[new_idx]
        self._state.set_brush(kind=new_kind)
        lang = language_wrapper.language_word_dict
        label = lang.get(f"paint_brush_kind_{new_kind}", new_kind.title())
        toast = getattr(self, "toast", None)
        if toast is not None:
            toast.info(
                lang.get("paint_brush_kind_changed", "Brush: {kind}").format(
                    kind=label,
                ),
                duration_ms=1500,
            )
        return new_kind

    def _maybe_offer_autosave_recovery(self) -> None:
        """Probe the autosave directory and prompt if anything is there.

        Pulled out as a method so a unit test can stub the snapshot
        list (instead of writing real bundles to ``~``) and verify
        the prompt routing. The prompt itself is a non-blocking
        toast — users in a hurry can ignore it; users who lost
        work can act on it via the recovery dialog.
        """
        try:
            snapshots = self.pending_autosaves()
        except (OSError, ValueError):
            return
        if not snapshots:
            return
        toast = getattr(self, "toast", None)
        lang = language_wrapper.language_word_dict
        msg = lang.get(
            "paint_autosave_recovery_available",
            "{n} autosave snapshot(s) available — File ▸ Restore",
        ).format(n=len(snapshots))
        if toast is not None:
            toast.warning(msg, duration_ms=6000)
            return
        status = getattr(self, "_status", None)
        if status is not None:
            status.showMessage(msg, 6000)

    def _on_image_loaded(self, w: int, h: int) -> None:
        msg = language_wrapper.language_word_dict.get(
            "paint_status_image_loaded", "Canvas: {w} × {h}",
        ).format(w=w, h=h)
        self._status.showMessage(msg, 3000)
        # First image landed on the canvas → the welcome hint has
        # done its job; tear it down so the user has clear sightlines
        # to whatever they just opened.
        self._dismiss_welcome_hint()
        # Image just landed → fresh content, no edits yet, so the
        # tab is clean. Setting this here covers both the File ▸ Open
        # path and any tool that calls ``canvas.load_image`` directly.
        self._set_tab_dirty(self._canvas, False)

    # ---- welcome hint -----------------------------------------------------

    def _build_welcome_hint(self) -> None:
        """Construct + parent the centred welcome panel.

        Built once and re-parented across tabs as the active canvas
        changes; the same widget is reused so signal wiring stays
        cheap. Visibility is toggled via :meth:`_dismiss_welcome_hint`
        on first real edit / image load.
        """
        from Imervue.paint.welcome_overlay import WelcomeHint
        lang = language_wrapper.language_word_dict
        self._welcome_hint = WelcomeHint(self._canvas)
        self._welcome_hint.set_translations(
            title=lang.get(
                "paint_welcome_title", "Drag an image or PSD here",
            ),
            subtitle=lang.get(
                "paint_welcome_subtitle", "or pick a starting point",
            ),
            new_label=lang.get("paint_welcome_new", "New tab"),
            open_label=lang.get("paint_welcome_open", "Open file…"),
            recent_label=lang.get("paint_welcome_recent", "Recent"),
        )
        self._welcome_hint.new_requested.connect(self._welcome_new_tab)
        self._welcome_hint.open_requested.connect(self._welcome_open_file)
        self._welcome_hint.recent_requested.connect(self._welcome_open_recent)
        self._refresh_welcome_recent()
        self._welcome_dismissed = False
        self._show_welcome_hint()
        # Keep the hint centred whenever the canvas widget changes
        # size — :class:`PaintCanvas` already emits resizes via Qt's
        # event chain so the eventFilter below picks them up.
        self._canvas.installEventFilter(self)

    def _refresh_welcome_recent(self) -> None:
        from Imervue.paint import recent_files
        if not hasattr(self, "_welcome_hint"):
            return
        self._welcome_hint.set_recent_paths(recent_files.paths())

    def _show_welcome_hint(self) -> None:
        if self._welcome_dismissed or not hasattr(self, "_welcome_hint"):
            return
        if self._welcome_hint.parent() is not self._canvas:
            self._welcome_hint.setParent(self._canvas)
        self._welcome_hint.position_centred(
            self._canvas.width(), self._canvas.height(),
        )
        self._welcome_hint.setVisible(True)
        self._welcome_hint.raise_()

    def _dismiss_welcome_hint(self) -> None:
        if not hasattr(self, "_welcome_hint"):
            return
        self._welcome_dismissed = True
        self._welcome_hint.setVisible(False)

    def _welcome_new_tab(self) -> None:
        self.new_tab()
        self._dismiss_welcome_hint()

    def _welcome_open_file(self) -> None:
        bridge = getattr(self, "_file_menu_bridge", None)
        if bridge is None:
            return
        if hasattr(bridge, "open_psd"):
            bridge.open_psd()
        self._dismiss_welcome_hint()

    def _welcome_open_recent(self, path: str) -> None:
        bridge = getattr(self, "_file_menu_bridge", None)
        if bridge is None:
            return
        if hasattr(bridge, "open_psd_at"):
            bridge.open_psd_at(path)
        self._dismiss_welcome_hint()

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

        Returns ``True`` when the event is consumed so Qt doesn't
        also dispatch it as a tab activate. Other event types fall
        through unchanged.
        """
        from PySide6.QtCore import Qt
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

    def _refresh_status_line(self) -> None:
        """Re-build the status bar from the latest hover + state.

        Called both from the hover signal and from
        :meth:`_on_state_event` so the line stays current when the
        user changes tool, brush size / opacity, or active layer
        without moving the cursor.
        """
        line = self._compose_status_line(self._last_hover)
        if not line:
            self._status.clearMessage()
            return
        self._status.showMessage(line)

    # Tools whose options live on BrushSettings and therefore want
    # the brush-size segment surfaced in the status bar.
    _BRUSHED_TOOLS = frozenset(
        {"brush", "eraser", "blur", "smudge", "clone_stamp"},
    )

    def _compose_status_line(self, hover: tuple[int, int] | None) -> str:
        """Build the rich status-bar string.

        Layout (left → right):
        ``Tool · x,y · Zoom% · CanvasW×H · Layer (i/n) · Opacity · Brush · Selection``.

        Each segment is omitted gracefully when its source is
        unavailable so a freshly-booted workspace with no document
        and no hover still renders a useful "Tool: brush" line.
        """
        lang = language_wrapper.language_word_dict
        segments: list[str] = []
        state = getattr(self, "_state", None)
        self._append_tool_segment(segments, state, lang)
        self._append_hover_segment(segments, hover, lang)
        self._append_canvas_segments(segments, lang)
        self._append_brush_segment(segments, state, lang)
        self._append_eyedropper_segment(segments, state, hover, lang)
        autosave_segment = self._format_autosave_segment(lang)
        if autosave_segment:
            segments.append(autosave_segment)
        return "    ".join(segments)

    @staticmethod
    def _append_tool_segment(segments, state, lang) -> None:
        if state is None:
            return
        tool_name = lang.get(
            f"paint_tool_{state.tool}",
            state.tool.replace("_", " ").title(),
        )
        segments.append(
            lang.get("paint_status_tool", "Tool: {name}").format(name=tool_name),
        )

    @staticmethod
    def _append_hover_segment(segments, hover, lang) -> None:
        if hover is None:
            return
        x, y = hover
        segments.append(
            lang.get("paint_status_cursor", "x: {x}  y: {y}").format(x=x, y=y),
        )

    def _append_canvas_segments(self, segments, lang) -> None:
        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            return
        zoom = getattr(canvas, "_zoom", None)
        if zoom is not None:
            segments.append(
                lang.get("paint_status_zoom", "{pct}%").format(
                    pct=int(round(float(zoom) * 100)),
                ),
            )
        document = canvas.document() if hasattr(canvas, "document") else None
        if document is not None:
            self._append_document_segments(segments, document, lang)

    def _append_brush_segment(self, segments, state, lang) -> None:
        if state is None or state.tool not in self._BRUSHED_TOOLS:
            return
        segments.append(
            lang.get(
                "paint_status_brush",
                "Brush: {size}px {opacity}%",
            ).format(
                size=int(state.brush.size),
                opacity=int(round(state.brush.opacity * 100)),
            ),
        )

    def _append_eyedropper_segment(self, segments, state, hover, lang) -> None:
        if state is None or state.tool != "eyedropper" or hover is None:
            return
        sampled = self._sample_eyedropper_at(hover)
        if sampled is None:
            return
        segments.append(
            lang.get(
                "paint_status_eyedrop", "Hover: #{hex} ({r},{g},{b})",
            ).format(
                hex=f"{sampled[0]:02X}{sampled[1]:02X}{sampled[2]:02X}",
                r=sampled[0], g=sampled[1], b=sampled[2],
            ),
        )

    def _sample_eyedropper_at(
        self, hover: tuple[int, int],
    ) -> tuple[int, int, int] | None:
        """Sample the colour under ``hover`` for the eyedropper preview.

        Honours :attr:`ToolState.eyedropper_sample_all_layers` — when
        on, reads the document composite (matches what the user sees
        on screen); when off, falls back to the active layer only,
        same as the click-commit behaviour.
        """
        canvas = getattr(self, "_canvas", None)
        if canvas is None or not hasattr(canvas, "document"):
            return None
        document = canvas.document()
        sample_all = getattr(
            self._state, "eyedropper_sample_all_layers", False,
        )
        if sample_all and hasattr(document, "composite"):
            arr = document.composite()
        else:
            active = (
                document.active_layer()
                if hasattr(document, "active_layer") else None
            )
            arr = active.image if active is not None else None
        if arr is None:
            return None
        x, y = hover
        h, w = arr.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return None
        pixel = arr[int(y), int(x)]
        return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

    def _format_autosave_segment(self, lang: dict) -> str | None:
        """Build the "Last autosaved Xs ago" status segment.

        Returns ``None`` when no autosave has ever fired in this
        session — the segment shouldn't pretend a snapshot exists.
        Picks the coarsest unit that fits ("just now" / "Xs ago" /
        "Xm ago" / "Xh ago") so the line stays compact at every age.
        """
        if self._last_autosave_at is None:
            return None
        import time
        elapsed = max(0.0, time.monotonic() - self._last_autosave_at)
        if elapsed < 5:
            label = lang.get(
                "paint_status_autosaved_just_now", "Saved just now",
            )
        elif elapsed < 60:
            label = lang.get(
                "paint_status_autosaved_seconds", "Saved {n}s ago",
            ).format(n=int(elapsed))
        elif elapsed < 3600:
            label = lang.get(
                "paint_status_autosaved_minutes", "Saved {n}m ago",
            ).format(n=int(elapsed // 60))
        else:
            label = lang.get(
                "paint_status_autosaved_hours", "Saved {n}h ago",
            ).format(n=int(elapsed // 3600))
        return label

    @staticmethod
    def _append_document_segments(
        segments: list[str], document, lang: dict,
    ) -> None:
        """Add the canvas-size / layer / selection segments in place."""
        shape = getattr(document, "shape", None)
        if shape is not None:
            h, w = shape
            segments.append(
                lang.get("paint_status_size", "{w}×{h}").format(w=w, h=h),
            )
        active = (
            document.active_layer() if hasattr(document, "active_layer") else None
        )
        if active is not None:
            PaintWorkspace._append_active_layer_segments(
                segments, document, active, lang,
            )
        if hasattr(document, "selection"):
            sel = document.selection()
            if sel is not None and bool(sel.any()):
                segments.append(
                    lang.get(
                        "paint_status_selection", "Sel {n}px",
                    ).format(n=int(sel.sum())),
                )

    @staticmethod
    def _append_active_layer_segments(
        segments: list[str], document, active, lang: dict,
    ) -> None:
        """Append the layer-name (with index/count) and per-layer opacity
        segments — split out so the parent method stays under the cognitive
        complexity threshold."""
        name = str(getattr(active, "name", "") or "")
        count = getattr(document, "layer_count", None)
        idx = (
            document.active_layer_index() + 1
            if hasattr(document, "active_layer_index") else None
        )
        if name and idx is not None and count:
            segments.append(
                lang.get(
                    "paint_status_layer",
                    "{name} ({i}/{n})",
                ).format(name=name, i=idx, n=count),
            )
        elif name:
            segments.append(name)
        opacity = getattr(active, "opacity", None)
        if opacity is not None and float(opacity) < 0.999:
            segments.append(
                lang.get(
                    "paint_status_layer_opacity", "Op {pct}%",
                ).format(pct=int(round(float(opacity) * 100))),
            )

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
        """Mark the navigator preview dirty and start the coalesce timer.

        Also refreshes the status line so layer-level changes
        (rename, opacity slider, active-layer switch, selection edit)
        update the layer + selection segments without waiting for
        the next hover event, and tears down the welcome hint on
        the first real edit so it doesn't linger on top of the
        user's strokes.
        """
        self._nav_dirty = True
        if not self._nav_timer.isActive():
            self._nav_timer.start()
        self._refresh_status_line()
        self._dismiss_welcome_hint()

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
