"""View-menu actions for the Paint workspace.

Six checkable toggles + two canvas-rotation actions:

* Pixel Grid (Ctrl+Shift+') — toggles the per-pixel grid overlay
  (only renders past PIXEL_GRID_MIN_ZOOM regardless of the toggle).
* Snap to Pixel — flips ToolState.snap_to_pixel so brush dabs
  centre on integer pixels.
* Onion Skin — flips a workspace-level flag that the canvas
  consults when blitting the animation overlay.
* Quick Mask (Q) — flips ToolState.quick_mask_active so the cursor
  switches to the documented red.
* Bleed Guides — toggles the trim/bleed/safe overlay on comic
  pages.
* Rotate Canvas CCW (Ctrl+Shift+H) — bumps the canvas view
  rotation by -15° around the widget centre.
* Reset Rotation — clears the canvas view rotation.

All toggles persist via ToolState's existing channels so the next
session starts where the last one ended.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace

logger = logging.getLogger("Imervue.paint.view_menu")


def populate_view_menu(workspace: PaintWorkspace) -> None:
    """Attach the View-menu actions to ``workspace``."""
    bridge = _ViewMenuBridge(workspace)
    workspace._view_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "view")
    lang = language_wrapper.language_word_dict
    bridge._actions = {}   # noqa: SLF001
    for key, fallback, slot, shortcut, checkable, initial in (
        ("paint_view_pixel_grid", "Pixel Grid",
         bridge.toggle_pixel_grid, "Ctrl+Shift+'", True,
         bridge.pixel_grid_active()),
        ("paint_view_snap_pixel", "Snap to Pixel",
         bridge.toggle_snap_to_pixel, "", True,
         bridge.snap_to_pixel_active()),
        ("paint_view_snap_edges", "Snap to Edges",
         bridge.toggle_snap_to_edges, "", True,
         bridge.snap_to_edges_active()),
        ("paint_view_onion_skin", "Onion Skin",
         bridge.toggle_onion_skin, "", True,
         bridge.onion_skin_active()),
        ("paint_view_quick_mask", "Quick Mask",
         bridge.toggle_quick_mask, "Q", True,
         bridge.quick_mask_active()),
        ("paint_view_bleed_guides", "Bleed Guides",
         bridge.toggle_bleed_guides, "", True,
         bridge.bleed_guides_active()),
        (None, None, None, None, None, None),
        ("paint_view_rotate_ccw", "Rotate Canvas CCW",
         bridge.rotate_canvas_ccw, "Ctrl+Shift+H", False, False),
        ("paint_view_reset_rotation", "Reset Rotation",
         bridge.reset_canvas_rotation, "", False, False),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        if checkable:
            action.setChecked(initial)
        action.triggered.connect(slot)
        bridge._actions[key] = action   # noqa: SLF001
    # Reflect zoom changes in the pixel-grid label so a checked
    # toggle still annotates "(zoom in)" when the current zoom is
    # below the visibility threshold. ``populate_view_menu`` runs
    # before the workspace finishes constructing its canvas, so we
    # defer the connection (and the first refresh) to the next
    # event-loop iteration — by which time ``workspace.canvas()``
    # is real and ``zoom_changed`` is wired up.
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, bridge.connect_canvas_signals)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _ViewMenuBridge:
    """Routes toggle actions to ToolState / canvas state."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace
        # Workspace-local flags for view-only toggles that don't yet
        # have a ToolState home (onion skin / bleed guides). Stored
        # here so a future commit can promote them without breaking
        # the menu wiring.
        if not hasattr(workspace, "_onion_skin_visible"):
            workspace._onion_skin_visible = False   # noqa: SLF001
        if not hasattr(workspace, "_bleed_guides_visible"):
            workspace._bleed_guides_visible = False   # noqa: SLF001
        if not hasattr(workspace, "_pixel_grid_visible"):
            workspace._pixel_grid_visible = False   # noqa: SLF001

    # ---- accessors used by the action initial state --------------------

    def pixel_grid_active(self) -> bool:
        return bool(getattr(self._workspace, "_pixel_grid_visible", False))

    def snap_to_pixel_active(self) -> bool:
        return bool(self._workspace.state().snap_to_pixel)

    def snap_to_edges_active(self) -> bool:
        return bool(self._workspace.state().snap_to_edges)

    def onion_skin_active(self) -> bool:
        return bool(getattr(self._workspace, "_onion_skin_visible", False))

    def quick_mask_active(self) -> bool:
        return bool(self._workspace.state().quick_mask_active)

    def bleed_guides_active(self) -> bool:
        return bool(getattr(self._workspace, "_bleed_guides_visible", False))

    # ---- toggles -------------------------------------------------------

    def toggle_pixel_grid(self, checked: bool) -> None:
        from Imervue.paint.visual_guides import (
            PIXEL_GRID_MIN_ZOOM,
            should_show_pixel_grid,
        )
        self._workspace._pixel_grid_visible = bool(checked)   # noqa: SLF001
        # The canvas owns the actual draw decision so the setter
        # short-circuits the repaint when nothing visually changes.
        canvas = self._workspace.canvas()
        if hasattr(canvas, "set_pixel_grid_visible"):
            canvas.set_pixel_grid_visible(bool(checked))
        else:   # pragma: no cover - older canvas builds
            canvas.update()
        # When the user enables the grid below the zoom threshold the
        # toggle has no visible effect — the renderer needs at least
        # ``PIXEL_GRID_MIN_ZOOM`` to draw lines that don't moire the
        # underlying art. Surface that as a status-bar tip so the
        # toggle doesn't read as broken.
        status = getattr(self._workspace, "_status", None)
        if checked and status is not None:
            zoom = float(getattr(canvas, "_zoom", 1.0))   # noqa: SLF001
            if not should_show_pixel_grid(zoom):
                msg = language_wrapper.language_word_dict.get(
                    "paint_status_pixel_grid_zoom_hint",
                    "Pixel grid: zoom in to {zoom_x}× to see the grid.",
                ).format(zoom_x=int(PIXEL_GRID_MIN_ZOOM))
                status.showMessage(msg, 4000)
        self.refresh_pixel_grid_label()

    def connect_canvas_signals(self) -> None:
        """Lazily connect to canvas signals once the workspace is built.

        ``populate_view_menu`` fires before the canvas attribute
        exists on the workspace, so the connection is deferred to a
        ``QTimer.singleShot(0, …)`` callback that lands after the
        rest of ``__init__`` finishes.
        """
        canvas = getattr(self._workspace, "_canvas", None)   # noqa: SLF001
        if canvas is None or not hasattr(canvas, "zoom_changed"):
            return
        canvas.zoom_changed.connect(
            lambda *_: self.refresh_pixel_grid_label(),
        )
        self.refresh_pixel_grid_label()

    def refresh_pixel_grid_label(self) -> None:
        """Append a "(zoom in)" suffix to the menu action when the
        toggle is on but the current zoom is below the threshold.

        Toast messages clear after a few seconds, so a user who
        flicked the toggle and then looked back at the menu would
        see only a checkmark and wonder why the grid isn't drawing.
        Reflecting the dormant state inside the menu keeps the cue
        visible for as long as the condition holds.

        The slot survives a workspace teardown that hasn't yet
        disconnected the canvas's ``zoom_changed`` signal — accessing
        the QAction whose C++ side has been freed throws
        ``RuntimeError`` from shiboken; we swallow it here rather
        than let the dangling slot abort the GC pass.
        """
        from Imervue.paint.visual_guides import (
            PIXEL_GRID_MIN_ZOOM,
            should_show_pixel_grid,
        )
        actions = getattr(self, "_actions", {})
        action = actions.get("paint_view_pixel_grid")
        if action is None:
            return
        lang = language_wrapper.language_word_dict
        base = lang.get("paint_view_pixel_grid", "Pixel Grid")
        canvas = getattr(self._workspace, "_canvas", None)   # noqa: SLF001
        zoom = float(getattr(canvas, "_zoom", 1.0))   # noqa: SLF001
        try:
            active = self.pixel_grid_active()
        except RuntimeError:
            return
        dormant = active and not should_show_pixel_grid(zoom)
        if dormant:
            suffix = lang.get(
                "paint_view_pixel_grid_dormant_suffix",
                "  (zoom in to {zoom_x}×)",
            ).format(zoom_x=int(PIXEL_GRID_MIN_ZOOM))
            new_text = base + suffix
        else:
            new_text = base
        try:
            action.setText(new_text)
        except RuntimeError:
            # The QAction's C++ side was freed (workspace teardown
            # raced ahead of the QTimer.singleShot we used to wire
            # this slot). Drop the reference so future calls
            # short-circuit on the ``action is None`` guard above.
            actions.pop("paint_view_pixel_grid", None)

    def toggle_snap_to_pixel(self, checked: bool) -> None:
        state = self._workspace.state()
        state.snap_to_pixel = bool(checked)
        # Use the existing private persistence path so the next
        # session starts with the same flag.
        state._persist()  # noqa: SLF001

    def toggle_snap_to_edges(self, checked: bool) -> None:
        state = self._workspace.state()
        state.snap_to_edges = bool(checked)
        state._persist()  # noqa: SLF001

    def toggle_onion_skin(self, checked: bool) -> None:
        self._workspace._onion_skin_visible = bool(checked)   # noqa: SLF001
        canvas = self._workspace.canvas()
        if hasattr(canvas, "set_onion_skin_visible"):
            canvas.set_onion_skin_visible(bool(checked))
        else:   # pragma: no cover - older canvas builds
            canvas.update()

    def toggle_quick_mask(self, checked: bool) -> None:
        state = self._workspace.state()
        state.quick_mask_active = bool(checked)
        state._persist()  # noqa: SLF001
        # Repaint so the cursor colour follows the new mode.
        self._workspace.canvas().update()

    def toggle_bleed_guides(self, checked: bool) -> None:
        self._workspace._bleed_guides_visible = bool(checked)   # noqa: SLF001
        canvas = self._workspace.canvas()
        # Seed a default JIS-B5 bleed guide on first toggle-on so the
        # overlay actually has geometry to draw. Older builds toggled
        # the flag but left ``_bleed_guides`` as None which silently
        # rendered nothing — the user's "doesn't work" complaint.
        if checked and getattr(canvas, "_bleed_guides", None) is None:
            import contextlib

            from Imervue.paint.bleed_guides import preset
            with contextlib.suppress(KeyError, AttributeError):
                canvas.set_bleed_guides(preset("manga_b5"))
        if hasattr(canvas, "set_bleed_guides_visible"):
            canvas.set_bleed_guides_visible(bool(checked))
        else:   # pragma: no cover - older canvas builds
            canvas.update()

    # ---- canvas rotation ----------------------------------------------

    def rotate_canvas_ccw(self) -> None:
        canvas = self._workspace.canvas()
        # Centre of the widget is the visual pivot the user expects
        # when triggering the action via the menu.
        try:
            canvas.set_rotation_around_centre(canvas.zoom_factor(), -15.0)
        except AttributeError:
            # Older canvas builds may not have the rotation method
            # yet — skip rather than crash. Phase 21g promotes the
            # canvas widget to honour the rotation.
            logger.debug("canvas does not support rotation yet")

    def reset_canvas_rotation(self) -> None:
        canvas = self._workspace.canvas()
        try:
            canvas.set_canvas_rotation(0.0)
        except AttributeError:
            logger.debug("canvas does not support rotation yet")
