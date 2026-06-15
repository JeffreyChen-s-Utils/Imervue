"""Dock construction + layout persistence for the Paint workspace.

Two collaborators live here:

* :class:`DockBuilder` — a one-shot construction helper invoked from the
  workspace constructor. It instantiates every right-side dock, wires the
  dock-owned signals back to the workspace, tabifies the three workflow
  clusters, assigns stable ``objectName``s and restores any saved layout.
  Pulling this ~150-line block out of ``__init__`` is the main lever that
  brings the workspace under the file-length budget.
* :class:`DockLayoutMixin` — the runtime layout commands (toggle-all,
  reset-to-default, save / restore state, window-menu toggles) that the
  workspace keeps exposing on its public surface.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.multi_language.language_wrapper import language_wrapper

DOCK_STATE_SETTING_KEY = "paint_workspace_dock_state"

# Stable objectName per dock attribute so ``QMainWindow.saveState()`` /
# ``restoreState()`` can match docks across launches. windowTitle is
# locale-translated and unstable, so Qt needs these explicit ids.
_DOCK_OBJECT_NAMES = {
    "_color_dock": "paint_dock_color",
    "_brush_dock": "paint_dock_brush",
    "_fill_dock": "paint_dock_fill",
    "_layer_dock": "paint_dock_layers",
    "_navigator_dock": "paint_dock_navigator",
    "_material_dock": "paint_dock_material",
    "_history_dock": "paint_dock_history",
    "_swatch_dock": "paint_dock_swatches",
    "_reference_dock": "paint_dock_reference",
    "_animation_dock": "paint_dock_animation",
    "_page_dock": "paint_dock_pages",
    "_stamp_dock": "paint_dock_stamps",
    "_pose_dock": "paint_dock_pose",
    "_histogram_dock": "paint_dock_histogram",
}

_CLUSTER_ORDER = ("drawing", "canvas", "library")


class DockBuilder:
    """Constructs and lays out every right-side dock for a workspace.

    Stateless beyond the workspace handle it is given; ``build`` mutates
    the workspace in place (the docks become ``_<name>_dock`` attributes)
    so the rest of the workspace keeps its existing attribute contract.
    """

    def __init__(self, workspace):
        self._ws = workspace

    def build(self) -> None:
        """Create the docks, tabify the clusters, and restore saved state."""
        ws = self._ws
        self._create_docks()
        clusters = self._cluster_layout()
        all_right_docks = (
            clusters["drawing"] + clusters["canvas"] + clusters["library"]
        )
        ws._install_dock_clusters(
            (clusters["drawing"], clusters["canvas"], clusters["library"]),
        )
        ws._dock_clusters = clusters
        self._assign_object_names(all_right_docks)
        ws._populate_window_menu()
        ws._restore_dock_state()

    def _create_docks(self) -> None:
        """Instantiate every dock + wire its signals back to the workspace."""
        ws = self._ws
        from Imervue.paint.dock_panels import (
            BrushDock,
            ColorDock,
            FillDock,
            HistoryDock,
            LayerDock,
            NavigatorDock,
        )
        ws._color_dock = ColorDock(ws._state, ws)
        ws._brush_dock = BrushDock(ws._state, ws)
        ws._fill_dock = FillDock(ws._state, ws)
        ws._fill_dock.set_auto_fill_callback(ws._auto_fill_closed_regions)
        ws._layer_dock = LayerDock(ws._canvas.document(), ws)
        ws._navigator_dock = NavigatorDock(ws)
        ws._history_dock = HistoryDock(ws)
        self._create_library_docks()
        self._create_extra_docks()

    def _create_library_docks(self) -> None:
        ws = self._ws
        from Imervue.paint.dock_panels import MaterialDock
        from Imervue.paint.material_library import default_material_index
        from Imervue.paint.swatch_panel import SwatchPanel
        ws._material_dock = MaterialDock(
            index=default_material_index(), parent=ws,
        )
        ws._material_dock.material_chosen.connect(ws._on_material_chosen)
        ws._swatch_dock = SwatchPanel(ws._state, ws)
        ws._swatch_dock.color_chosen.connect(
            lambda r, g, b: ws._state.set_foreground((r, g, b), commit=False),
        )
        from Imervue.paint.reference_dock import ReferenceDock
        ws._reference_dock = ReferenceDock(ws)
        from Imervue.paint.histogram_dock import HistogramDock
        ws._histogram_dock = HistogramDock(ws)

    def _create_extra_docks(self) -> None:
        """Animation timeline + comic project / stamp / pose docks."""
        ws = self._ws
        from Imervue.paint.animation_dock import AnimationDock
        ws._animation_dock = AnimationDock(parent=ws)
        ws._animation_dock.add_frame_requested.connect(
            ws._on_animation_add_frame,
        )
        ws._animation_dock.remove_frame_requested.connect(
            ws._on_animation_remove_frame,
        )
        ws._animation_dock.frame_selected.connect(
            ws._on_animation_frame_selected,
        )
        from Imervue.paint.page_dock import PageDock
        ws._page_dock = PageDock(ws, parent=ws)
        ws._page_dock.page_selected.connect(ws._on_page_selected)
        from Imervue.paint.stamp_dock import StampDock
        ws._stamp_dock = StampDock(parent=ws)
        ws._stamp_dock.stamp_chosen.connect(ws._on_stamp_chosen)
        from Imervue.paint.pose_dock import PoseDock
        ws._pose_dock = PoseDock(parent=ws)
        ws._pose_dock.insert_requested.connect(ws._on_pose_insert)

    def _cluster_layout(self) -> dict:
        """Group the docks into the three workflow clusters.

        Three scannable tab rows ("drawing tools / canvas data /
        libraries") rather than one fourteen-tab pile, while keeping the
        same vertical budget (only the tallest dock drives the column's
        minimum).
        """
        ws = self._ws
        return {
            "drawing": (
                ws._color_dock,
                ws._brush_dock,
                ws._fill_dock,
                ws._swatch_dock,
            ),
            "canvas": (
                ws._layer_dock,
                ws._navigator_dock,
                ws._history_dock,
                ws._page_dock,
                ws._animation_dock,
                ws._histogram_dock,
            ),
            "library": (
                ws._material_dock,
                ws._stamp_dock,
                ws._pose_dock,
                ws._reference_dock,
            ),
        }

    def _assign_object_names(self, all_right_docks) -> None:
        ws = self._ws
        attr_by_id = {
            id(getattr(ws, attr)): name
            for attr, name in _DOCK_OBJECT_NAMES.items()
        }
        for dock in all_right_docks:
            dock.setObjectName(attr_by_id[id(dock)])
            dock.setFeatures(
                dock.features()
                | dock.DockWidgetFeature.DockWidgetMovable
                | dock.DockWidgetFeature.DockWidgetFloatable,
            )


class DockLayoutMixin:
    """Runtime dock-layout commands kept on the workspace's public surface.

    Expects the host to provide ``_dock_clusters`` (built by
    :class:`DockBuilder`) and to be a ``QMainWindow``.
    """

    DOCK_STATE_SETTING_KEY = DOCK_STATE_SETTING_KEY

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

    def toggle_all_docks(self) -> bool:
        """Hide every right-side dock for distraction-free painting,
        or restore them when called again.

        Industry-standard "Tab" key behaviour. Returns the new
        visibility state so callers can update menu check-marks.

        State is tracked per-call via :attr:`_docks_collapsed` so the
        second invocation restores the exact set of docks that were
        visible before; a dock the user had already hidden via its
        corner X stays hidden after the un-toggle.
        """
        clusters = getattr(self, "_dock_clusters", None)
        if not clusters:
            return False
        all_docks = self._ordered_docks(clusters)
        collapsed = getattr(self, "_docks_collapsed", None)
        if collapsed is None:
            self._docks_collapsed = {
                dock: (not dock.isHidden()) for dock in all_docks
            }
            for dock in all_docks:
                if not dock.isHidden():
                    dock.setVisible(False)
            return False
        for dock, was_visible in collapsed.items():
            dock.setVisible(was_visible)
        self._docks_collapsed = None
        return True

    @staticmethod
    def _ordered_docks(clusters: dict) -> tuple:
        """Flatten the three clusters into their canonical left-to-right
        order — shared by toggle-all and reset-layout."""
        return tuple(
            dock
            for name in _CLUSTER_ORDER
            for dock in clusters.get(name, ())
        )

    def reset_workspace_layout(self) -> None:
        """Re-apply the default three-cluster layout.

        Drops any saved state (so the next launch also starts on the
        default), removes every right-side dock from its current home,
        then re-tabifies the three clusters in their canonical order.
        """
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        user_setting_dict.pop(self.DOCK_STATE_SETTING_KEY, None)
        clusters = getattr(self, "_dock_clusters", None)
        if not clusters:
            return
        for dock in self._ordered_docks(clusters):
            self.removeDockWidget(dock)
        for cluster_name in _CLUSTER_ORDER:
            self._reinstall_cluster(clusters.get(cluster_name, ()))

    def _reinstall_cluster(self, cluster: tuple) -> None:
        if not cluster:
            return
        anchor = cluster[0]
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, anchor)
        anchor.show()
        for dock in cluster[1:]:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            self.tabifyDockWidget(anchor, dock)
            dock.show()
        anchor.raise_()

    def _populate_window_menu(self) -> None:
        """Checkable dock toggles grouped into three cluster submenus.

        Each toggle's check state mirrors the dock's ``isVisible`` so
        closing a dock via its corner X also unchecks the entry.
        """
        from Imervue.paint.paint_menu_bar import menu_for
        lang = language_wrapper.language_word_dict
        menu = menu_for(self, "window")
        self._window_dock_actions = {}
        for cluster_key in _CLUSTER_ORDER:
            title_key, title_fallback = _CLUSTER_TITLES[cluster_key]
            submenu = menu.addMenu(lang.get(title_key, title_fallback))
            for key, fallback, dock in self._window_cluster_entries()[cluster_key]:
                self._add_dock_toggle(submenu, key, fallback, dock, lang)
        self._add_window_view_actions(menu, lang)

    def _window_cluster_entries(self) -> dict:
        return {
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

    def _add_dock_toggle(self, submenu, key, fallback, dock, lang) -> None:
        action = submenu.addAction(lang.get(key, fallback))
        action.setCheckable(True)
        action.setChecked(dock.isVisible() or True)
        action.triggered.connect(
            lambda checked, d=dock: d.setVisible(bool(checked)),
        )
        # Reflect external close (dock corner X). Wrap the setChecked
        # call so a teardown that frees the QAction's C++ side before
        # the dock's signal fully disconnects doesn't leave a dangling
        # RuntimeError-raising slot in the queue.
        dock.visibilityChanged.connect(
            lambda visible, a=action: _safe_set_checked(a, visible),
        )
        self._window_dock_actions[key] = action

    def _add_window_view_actions(self, menu, lang) -> None:
        """Append the standalone-view + reset-layout entries below the
        dock toggles."""
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
        menu.addSeparator()
        reset_action = menu.addAction(lang.get(
            "paint_window_reset_layout", "Reset Workspace Layout",
        ))
        reset_action.triggered.connect(self.reset_workspace_layout)


_CLUSTER_TITLES = {
    "drawing": ("paint_window_group_drawing", "Drawing"),
    "canvas": ("paint_window_group_canvas", "Canvas"),
    "library": ("paint_window_group_library", "Library"),
}


def _safe_set_checked(action, value: bool) -> None:
    """Best-effort ``QAction.setChecked`` that survives shiboken teardown.

    Dock-visibility signals stay connected during workspace
    ``deleteLater()``; the C++ QAction can be freed before the
    signal-disconnect propagates, leaving a queued slot that would
    otherwise abort the GC pass with ``RuntimeError: Internal C++
    object already deleted``.
    """
    try:
        action.setChecked(bool(value))
    except RuntimeError:
        return
