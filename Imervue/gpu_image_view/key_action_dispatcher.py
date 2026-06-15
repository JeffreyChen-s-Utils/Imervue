"""Keyboard-action routing for the viewer.

``GPUImageView.keyPressEvent`` resolves a key chord to an action *name* via
``shortcut_manager`` and then hands that name to :class:`KeyActionDispatcher`,
which routes it to the right view operation. Splitting this table-driven
dispatch out of the widget keeps the GL widget focused on rendering and event
plumbing, and lets the pure routing helpers be unit-tested without Qt.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from Imervue.gpu_image_view.actions.delete import undo_delete
from Imervue.gpu_image_view.actions.goto_dialog import open_goto_dialog
from Imervue.gpu_image_view.actions.keyboard_actions import (
    copy_image_to_clipboard,
    rate_current_image,
    toggle_favorite,
    toggle_fullscreen,
    trash_current_image,
    trash_selected_tiles,
)
from Imervue.gpu_image_view.actions.search_dialog import open_search_dialog
from Imervue.gpu_image_view.actions.slideshow import open_slideshow_dialog
from Imervue.gui.annotation_dialog import open_annotation_for_path

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_COLOR_MODE_NAMES = ["Normal", "Grayscale", "Invert", "Sepia"]
_COLOR_MODE_KEYS = [
    "color_mode_normal", "color_mode_grayscale",
    "color_mode_invert", "color_mode_sepia",
]
_COLOR_MODE_COUNT = 4
_RATING_ACTIONS = {"rate_1", "rate_2", "rate_3", "rate_4", "rate_5"}
_CULL_STATES = {"cull_pick": "pick", "cull_reject": "reject",
                "cull_unflag": "unflagged"}
_ANIM_SPEED_FACTORS = {"anim_slower": 1 / 1.5, "anim_faster": 1.5}


def next_color_mode(current: int) -> int:
    """Return the next colour mode index, wrapping at the mode count."""
    return (current + 1) % _COLOR_MODE_COUNT


def color_mode_labels(index: int) -> tuple[str, str]:
    """Return ``(lang_key, fallback_text)`` for a colour-mode index."""
    return _COLOR_MODE_KEYS[index], _COLOR_MODE_NAMES[index]


def cull_state_for(action: str) -> str | None:
    """Map a culling action name to its state, or None when not a cull action."""
    return _CULL_STATES.get(action)


def anim_speed_factor(action: str) -> float | None:
    """Return the speed multiplier for an animation-speed action, else None."""
    return _ANIM_SPEED_FACTORS.get(action)


class KeyActionDispatcher:
    """Routes resolved shortcut action names to view operations."""

    def __init__(self, view: GPUImageView) -> None:
        self.view = view

    # ------------------------------------------------------------------
    # Top-level dispatch
    # ------------------------------------------------------------------
    def dispatch(self, action: str, modifiers) -> None:
        if self._dispatch_simple(action):
            return
        if self._dispatch_toggle(action, modifiers):
            return
        if self._dispatch_culling(action):
            return
        if self._dispatch_image(action):
            return
        anim = self.view._animation
        if anim and anim.is_animated:
            self._dispatch_anim(action)

    # ------------------------------------------------------------------
    # Simple 1:1 actions
    # ------------------------------------------------------------------
    def _dispatch_simple(self, action: str) -> bool:
        """Actions that map 1:1 to a function call with no condition."""
        view = self.view
        if action in _RATING_ACTIONS:
            rate_current_image(view, int(action[-1]))
            return True
        handler = {
            "undo": self._do_undo,
            "redo": view.undo_manager.redo,
            "redo_alt": view.undo_manager.redo,
            "copy": lambda: copy_image_to_clipboard(view),
            "paste": view._paste_image_from_clipboard,
            "search": lambda: open_search_dialog(view),
            "search_alt": lambda: open_search_dialog(view),
            "goto": lambda: open_goto_dialog(view),
            "fullscreen": lambda: toggle_fullscreen(view),
            "random_image": view.jump_to_random_image,
            "command_palette": self._open_command_palette,
            "macro_replay": self._replay_macro,
            "slideshow": lambda: open_slideshow_dialog(view),
            "tags": self._open_tag_album,
            "favorite": lambda: toggle_favorite(view),
            "history_back": self._history_back_toast,
            "history_forward": self._history_forward_toast,
        }.get(action)
        if handler is None:
            return False
        handler()
        return True

    def _do_undo(self) -> None:
        view = self.view
        if view.undo_manager.canUndo():
            view.undo_manager.undo()
        else:
            undo_delete(main_gui=view)

    def _open_command_palette(self) -> None:
        from Imervue.gui.command_palette import open_command_palette
        open_command_palette(self.view.main_window)

    def _replay_macro(self) -> None:
        from Imervue.macros.macro_manager import replay_last_macro
        replay_last_macro(self.view.main_window)

    def _open_tag_album(self) -> None:
        from Imervue.gui.tag_album_dialog import open_tag_album_dialog
        open_tag_album_dialog(self.view)

    def _history_back_toast(self) -> None:
        if not self.view.history_back():
            self.view._toast("history_at_start", "At start of history")

    def _history_forward_toast(self) -> None:
        if not self.view.history_forward():
            self.view._toast("history_at_end", "At end of history")

    # ------------------------------------------------------------------
    # View-mode toggles
    # ------------------------------------------------------------------
    def _dispatch_toggle(self, action: str, modifiers) -> bool:
        """View-mode toggles: theater, pixel_view, split, dual, multi, colour."""
        toggle_handlers = {
            "theater": self._toggle_theater_mode,
            "pixel_view": self._toggle_pixel_view,
            "split_view": self._toggle_split_view,
            "dual_page": lambda: self._toggle_dual_page(modifiers),
            "multi_monitor": self._toggle_multi_monitor,
            "color_mode_cycle": self._cycle_color_mode,
            "loupe": self._toggle_loupe,
            "reading_mode": self._toggle_reading_mode,
        }
        handler = toggle_handlers.get(action)
        if handler is None:
            return False
        handler()
        return True

    def _toggle_theater_mode(self) -> None:
        mw = self.view.main_window
        if hasattr(mw, "toggle_theater_mode"):
            mw.toggle_theater_mode()

    def _toggle_pixel_view(self) -> None:
        view = self.view
        if not view.deep_zoom:
            return
        view._pixel_view = not view._pixel_view
        if view._pixel_view:
            view._toast("pixel_view_hint",
                        "Pixel view — zoom in to ≥400% to see grid")
        view.update()

    def _toggle_split_view(self) -> None:
        mw = self.view.main_window
        if hasattr(mw, "activate_dual_view"):
            mw.activate_dual_view("split")

    def _toggle_dual_page(self, modifiers) -> None:
        mw = self.view.main_window
        if not hasattr(mw, "activate_dual_view"):
            return
        mode = ("manga_rtl"
                if modifiers & Qt.KeyboardModifier.ControlModifier
                else "manga")
        mw.activate_dual_view(mode)

    def _toggle_multi_monitor(self) -> None:
        mw = self.view.main_window
        if hasattr(mw, "toggle_multi_monitor_window"):
            mw.toggle_multi_monitor_window()

    def _cycle_color_mode(self) -> None:
        view = self.view
        view.renderer.color_mode = next_color_mode(view.renderer.color_mode)
        key, fallback = color_mode_labels(view.renderer.color_mode)
        view._toast(key, fallback)
        view.update()

    def _toggle_loupe(self) -> None:
        """Cursor-following magnifier; deep zoom only."""
        view = self.view
        if not view.deep_zoom:
            return
        view._loupe_enabled = not view._loupe_enabled
        if view._loupe_enabled:
            view._toast("loupe_on", "Loupe on — magnifier follows cursor")
        else:
            view._toast("loupe_off", "Loupe off")
        view.update()

    def _toggle_reading_mode(self) -> None:
        """Fit-width vertical reading mode; deep zoom only."""
        view = self.view
        if not view.deep_zoom:
            return
        view._reading_mode = not view._reading_mode
        if view._reading_mode:
            view._browse.apply_reading_fit()
            view._toast("reading_on", "Reading mode — scroll to read, auto-advance")
        else:
            view._fit_to_window()
            view._toast("reading_off", "Reading mode off")
        view.update()

    # ------------------------------------------------------------------
    # Culling
    # ------------------------------------------------------------------
    def _dispatch_culling(self, action: str) -> bool:
        state = cull_state_for(action)
        if state is None:
            return False
        self.view._apply_cull_state(state)
        return True

    # ------------------------------------------------------------------
    # Current-image operations
    # ------------------------------------------------------------------
    def _dispatch_image(self, action: str) -> bool:
        """Current-image ops: edit, histogram, fit, bookmark, rotate, reset, delete."""
        view = self.view
        handler = {
            "edit": self._edit_current_image,
            "histogram": self._toggle_histogram,
            "fit_width": self._fit_width_with_toast,
            "fit_height": self._fit_height_with_toast,
            "fit_window": view._fit_window_with_toast,
            "zoom_in": lambda: view._zoom_step(True),
            "zoom_out": lambda: view._zoom_step(False),
            "bookmark": self._bookmark_if_deep_zoom,
            "rotate_cw": lambda: self._push_rotate(True),
            "rotate_ccw": lambda: self._push_rotate(False),
            "reset_view": self._reset_view,
            "delete": self._delete_current,
        }.get(action)
        if handler is None:
            return False
        handler()
        return True

    def _push_rotate(self, clockwise: bool) -> None:
        view = self.view
        if not view.deep_zoom:
            return
        from Imervue.gpu_image_view.actions.undo_commands import RotateCommand
        view.undo_manager.push(RotateCommand(view, clockwise=clockwise))

    def _reset_view(self) -> None:
        """Home key — back to the "whole image visible" baseline.

        Deep zoom fits-to-window (NOT 100 % top-left: the reset state the
        user expects is the same centred fit shown when an image opens);
        the tile grid scrolls back to its origin.
        """
        view = self.view
        if view.deep_zoom:
            view._fit_to_window()
        elif view.tile_grid_mode:
            view.grid_offset_x = 0
            view.grid_offset_y = 0
        view.update()

    def _edit_current_image(self) -> None:
        view = self.view
        if not view.deep_zoom:
            return
        images = view.model.images
        if images and 0 <= view.current_index < len(images):
            open_annotation_for_path(view, images[view.current_index])

    def _toggle_histogram(self) -> None:
        view = self.view
        if view.deep_zoom:
            view._show_histogram = not view._show_histogram
            view.update()

    def _fit_width_with_toast(self) -> None:
        view = self.view
        if view.deep_zoom:
            view._fit_to_width()
            view._toast("fit_width", "Fit Width")

    def _fit_height_with_toast(self) -> None:
        view = self.view
        if view.deep_zoom:
            view._fit_to_height()
            view._toast("fit_height", "Fit Height")

    def _bookmark_if_deep_zoom(self) -> None:
        view = self.view
        if view.deep_zoom:
            view._toggle_bookmark()

    def _delete_current(self) -> None:
        view = self.view
        if view.tile_grid_mode and view.tile_selection_mode:
            trash_selected_tiles(view)
        elif view.deep_zoom:
            trash_current_image(view)

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _dispatch_anim(self, action: str) -> None:
        view = self.view
        anim = view._animation
        if action == "anim_toggle":
            anim.toggle()
        elif action == "anim_prev":
            anim.prev_frame()
        elif action == "anim_next":
            anim.next_frame()
        else:
            factor = anim_speed_factor(action)
            if factor is None:
                return
            anim.set_speed(anim.speed * factor)
            mw = view.main_window
            if hasattr(mw, "toast"):
                mw.toast.info(f"Speed: {anim.speed:.2f}x")
