"""Hover, pan, drag-select and tile activation for the GPU view.

Mixed into :class:`~Imervue.gpu_image_view.input_controller.InputController`;
reads and mutates the live view through ``self._view``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from Imervue.gpu_image_view.actions.select import select_tiles_in_rect

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_EPSILON = 1e-9


class InputTileMixin:
    """Pointer pan, tile-wall selection and tile activation behaviour."""

    _view: GPUImageView

    # -- move / drag --------------------------------------------------

    def update_hover_state(self, event) -> None:
        view = self._view
        # hover 圖片像素座標（status bar 用）
        if view.deep_zoom and not view.tile_grid_mode:
            mx, my = event.position().x(), event.position().y()
            img_x = int((mx - view.dz_offset_x) / max(view.zoom, _EPSILON))
            img_y = int((my - view.dz_offset_y) / max(view.zoom, _EPSILON))
            view._hover_image_xy = (img_x, img_y)
            view._update_status_info()
            if view._loupe_enabled:
                view.update()  # repaint so the magnifier tracks the cursor
        if view.tile_grid_mode:
            mx, my = event.position().x(), event.position().y()
            view._hover_tile_path = self.tile_at(mx, my)
            view._update_hover_preview(event)
            if view._loupe_enabled and view._hover_tile_path:
                view.update()

    def handle_middle_drag(self, delta) -> None:
        view = self._view
        if view.tile_grid_mode:
            view.grid_offset_x += delta.x()
            view.grid_offset_y += delta.y()
            view._clamp_grid_scroll()
        elif view.deep_zoom:
            view.dz_offset_x += delta.x()
            view.dz_offset_y += delta.y()
            view._browse.clamp_pan()
            view._user_locked_view = True
            view._last_pan_velocity = (delta.x(), delta.y())
        view.update()

    def start_pan_momentum(self) -> None:
        """Fling the deep-zoom image after a middle-drag release."""
        view = self._view
        if view._smooth_nav_enabled and view.deep_zoom:
            view._pan_momentum.start(*view._last_pan_velocity)

    def handle_left_drag_select(self, event) -> None:
        from PySide6.QtCore import Qt
        view = self._view
        if not (
            view.tile_grid_mode
            and event.buttons() & Qt.MouseButton.LeftButton
            and view._drag_start_pos
        ):
            return
        if not view._drag_selecting and not self._try_begin_drag_select(event):
            return
        view._drag_end_pos = event.position()
        view.update()

    def _try_begin_drag_select(self, event) -> bool:
        """Return True once the drag threshold has been exceeded and a frame-
        selection has started. Returns False while still below threshold or
        when the gesture was consumed by drag-out."""
        view = self._view
        move_delta = event.position() - view._drag_start_pos
        if move_delta.manhattanLength() < QApplication.startDragDistance():
            return False
        from Imervue.gpu_image_view.actions.drag_out import try_start_drag_out
        if try_start_drag_out(view, view._drag_start_pos):
            view._drag_start_pos = None
            view._drag_end_pos = None
            return False
        view.tile_selection_mode = True
        view._drag_selecting = True
        return True

    # -- release / tile activation ------------------------------------

    def handle_tile_release(self, event) -> bool:
        view = self._view
        if view._drag_selecting:
            self.finish_drag_select()
            return True
        # A click, not a drag: the press point is spent. Left set, it read as a
        # drag in progress and switched the hover preview - and the hovered-tile
        # target of the rating / label / cull keys - off for good.
        view._drag_start_pos = None
        view._drag_end_pos = None
        mx, my = event.position().x(), event.position().y()
        clicked_tile = self.tile_at(mx, my)
        if not clicked_tile:
            return False
        if not view.tile_selection_mode:
            self.enter_deep_zoom(clicked_tile)
            return True
        self.toggle_tile_selection(clicked_tile)
        return True

    def finish_drag_select(self) -> None:
        view = self._view
        select_tiles_in_rect(view._drag_start_pos, view._drag_end_pos, view)
        view._drag_selecting = False
        view._drag_start_pos = None
        view._drag_end_pos = None
        view.update()

    def tile_at(self, mx: float, my: float) -> str | None:
        for x0, y0, x1, y1, path in self._view.tile_rects:
            if x0 <= mx <= x1 and y0 <= my <= y1:
                return path
        return None

    def enter_deep_zoom(self, path: str) -> None:
        from Imervue.gpu_image_view.tile_loader import image_is_current
        view = self._view
        # The clicked tile can already be gone from the model — the folder
        # dropped it (delete / filter / stack collapse / watch-folder refresh)
        # after the wall was last painted but before this click, and its rect
        # lingers one frame. Opening the vanished path would leave the wall to
        # start a load the completion guard then discards, stranding a stuck
        # "Loading…" view. Ignore the stale click and stay on the wall.
        if not image_is_current(view, path):
            return
        view._saved_tile_state = {
            "grid_offset_x": view.grid_offset_x,
            "grid_offset_y": view.grid_offset_y,
            "tile_scale": view.tile_scale,
        }
        view.tile_grid_mode = False
        queue = getattr(view, "_tile_queue", None)
        view.current_index = (queue.positions[path] if queue is not None
                              else view.model.images.index(path))
        view.load_deep_zoom_image(path)

    def toggle_tile_selection(self, path: str) -> None:
        view = self._view
        if path in view.selected_tiles:
            view.selected_tiles.remove(path)
        else:
            view.selected_tiles.add(path)
        view.update()
