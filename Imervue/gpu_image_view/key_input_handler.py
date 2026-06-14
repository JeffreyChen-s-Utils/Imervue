"""Keyboard event handling for :class:`GPUImageView`.

The Qt ``keyPressEvent`` override stays on the QWidget subclass as a thin
forwarder; this handler holds the routing: F8 HUD toggle, F1-F5 colour
labels, Escape (exit deep-zoom / clear selection / leave fullscreen),
arrow-key navigation, and the configurable-shortcut dispatch fallback.

It reads and mutates view state directly and routes the remaining actions
through the view's :class:`KeyActionDispatcher`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from Imervue.gpu_image_view.actions.keyboard_actions import toggle_fullscreen
from Imervue.gpu_image_view.actions.select import (
    switch_to_next_folder,
    switch_to_next_image,
    switch_to_previous_folder,
    switch_to_previous_image,
)
from Imervue.gpu_image_view.actions.slideshow import stop_slideshow
from Imervue.gpu_image_view.tile_focus import (
    DOWN,
    LEFT,
    NO_FOCUS,
    RIGHT,
    UP,
    next_focus_index,
    scroll_offset_to_reveal,
)
from Imervue.gpu_image_view.tile_layout import tile_grid_layout

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# F1-F5 → colour labels (red/yellow/green/blue/purple).
COLOR_LABEL_KEYS = {
    Qt.Key.Key_F1: "red",
    Qt.Key.Key_F2: "yellow",
    Qt.Key.Key_F3: "green",
    Qt.Key.Key_F4: "blue",
    Qt.Key.Key_F5: "purple",
}
_ARROW_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right)
_ARROW_DIRECTIONS = {
    Qt.Key.Key_Left: LEFT,
    Qt.Key.Key_Right: RIGHT,
    Qt.Key.Key_Up: UP,
    Qt.Key.Key_Down: DOWN,
}
_ENTER_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)


class KeyInputHandler:
    """Route key presses to viewer behaviour."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view

    def handle(self, event) -> None:
        from Imervue.gui.shortcut_settings_dialog import shortcut_manager

        view = self._view
        key = event.key()
        modifiers = event.modifiers()

        if (hasattr(view.main_window, "plugin_manager")
                and view.main_window.plugin_manager.dispatch_key_press(
                    key, modifiers, view)):
            return

        if self._handle_builtin(key, modifiers):
            return

        mods_int = modifiers.value if hasattr(modifiers, "value") else int(modifiers)
        action = shortcut_manager.get_action(key, mods_int)
        if action is None:
            return
        view._key_dispatch.dispatch(action, modifiers)

    def _handle_builtin(self, key, modifiers) -> bool:
        """Handle the hard-wired keys; returns True when consumed."""
        if key == Qt.Key.Key_F8:
            self._toggle_hud(modifiers)
            return True
        no_ctrl_alt = not (modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier))
        if key in COLOR_LABEL_KEYS and no_ctrl_alt:
            self._view._apply_color_label(COLOR_LABEL_KEYS[key])
            return True
        if key == Qt.Key.Key_Escape and self._handle_escape():
            return True
        if key in _ENTER_KEYS and self._activate_focused_tile():
            return True
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier
        return key in _ARROW_KEYS and self._handle_arrow_keys(key, modifiers, shift)

    def _toggle_hud(self, modifiers) -> None:
        view = self._view
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            view._show_debug_hud = not view._show_debug_hud
        else:
            view._show_osd = not view._show_osd
        view.update()

    def _handle_escape(self) -> bool:
        """Returns True if Escape was handled."""
        view = self._view
        if getattr(view, "_slideshow", None) and view._slideshow.running:
            stop_slideshow(view)
            return True
        if view.main_window.isFullScreen():
            toggle_fullscreen(view)
            return True
        if view.tile_grid_mode and view.selected_tiles:
            view.tile_selection_mode = False
            view.selected_tiles.clear()
            view.update()
            return True
        if view.deep_zoom or view.active_deep_zoom_worker:
            self.exit_deep_zoom_to_grid()
            return True
        return False

    def exit_deep_zoom_to_grid(self) -> None:
        view = self._view
        view._cancel_deep_zoom_worker()
        view._cancel_all_prefetch()
        # Thumbnail size changed while zoomed in → the cached tiles are the
        # old size, so rebuild the grid at the new size instead of restoring
        # the stale layout (which would mismatch the new cell metrics).
        if view._tile_size_dirty and view.model.images:
            view._tile_size_dirty = False
            view._saved_tile_state = None
            view.clear_tile_grid()
            view.load_tile_grid_async(image_paths=view.model.images)
        else:
            self._restore_grid_state()
        # 回到縮圖牆時，把游標標在剛才檢視的那張，讓使用者保留瀏覽位置
        self._focus_current_if_valid()
        # 若使用者偏好清單瀏覽，Esc 後切回 list 而非 tile grid
        if hasattr(view.main_window, "after_deep_zoom_escape"):
            view.main_window.after_deep_zoom_escape()
        view.update()

    def _restore_grid_state(self) -> None:
        view = self._view
        view._clear_deep_zoom()
        view.tile_grid_mode = True
        saved = view._saved_tile_state
        if saved:
            view.grid_offset_x = saved["grid_offset_x"]
            view.grid_offset_y = saved["grid_offset_y"]
            view.tile_scale = saved["tile_scale"]
            view._saved_tile_state = None

    def _handle_arrow_keys(self, key, modifiers, shift) -> bool:
        view = self._view
        ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        if ctrl and shift and self._handle_folder_jump(key):
            return True
        if view.tile_grid_mode:
            self._move_grid_focus(key)
            return True
        if view.deep_zoom:
            return self._switch_image_by_arrow(key)
        return False

    def _handle_folder_jump(self, key) -> bool:
        """Ctrl+Shift+Left/Right → jump to sibling folder. Returns True on hit."""
        view = self._view
        if key == Qt.Key.Key_Right:
            switch_to_next_folder(main_gui=view)
            return True
        if key == Qt.Key.Key_Left:
            switch_to_previous_folder(main_gui=view)
            return True
        return False

    def _grid_layout(self) -> tuple[float, float, float, int]:
        """Current thumbnail-wall layout as ``(base_tile, draw_scale, cell, cols)``."""
        view = self._view
        base_tile = view._tile_renderer.base_size()
        draw_scale, cell, cols = tile_grid_layout(
            view.width(), base_tile, view.tile_scale,
            view.tile_padding, view.devicePixelRatio(),
        )
        return base_tile, draw_scale, cell, cols

    def _move_grid_focus(self, key) -> None:
        """Arrow keys move the keyboard focus cursor across the thumbnail wall,
        scrolling the wall so the focused tile stays fully visible."""
        view = self._view
        count = len(view.model.images)
        if count == 0:
            return
        base_tile, draw_scale, cell, cols = self._grid_layout()
        view.focused_tile_index = next_focus_index(
            view.focused_tile_index, _ARROW_DIRECTIONS[key], cols, count,
        )
        view.grid_offset_y = scroll_offset_to_reveal(
            view.focused_tile_index, cols, cell, base_tile * draw_scale,
            view.grid_offset_y, view.height(),
        )
        view.update()

    def _activate_focused_tile(self) -> bool:
        """Enter on the thumbnail wall opens the focused tile (or toggles its
        selection while in selection mode). Returns True when a tile was acted on."""
        view = self._view
        if not view.tile_grid_mode:
            return False
        images = view.model.images
        idx = view.focused_tile_index
        if not 0 <= idx < len(images):
            return False
        path = images[idx]
        if view.tile_selection_mode:
            view._input.toggle_tile_selection(path)
        else:
            view._input.enter_deep_zoom(path)
        return True

    def _focus_current_if_valid(self) -> None:
        """Highlight the tile we were just viewing after leaving deep zoom."""
        view = self._view
        count = len(view.model.images)
        view.focused_tile_index = (
            view.current_index if 0 <= view.current_index < count else NO_FOCUS
        )

    def _switch_image_by_arrow(self, key) -> bool:
        """Left / Right → previous / next image in deep zoom. True on hit."""
        view = self._view
        if key == Qt.Key.Key_Right:
            switch_to_next_image(main_gui=view)
            return True
        if key == Qt.Key.Key_Left:
            switch_to_previous_image(main_gui=view)
            return True
        return False
