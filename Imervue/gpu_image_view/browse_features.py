"""Deep-zoom browse-feature behaviour for :class:`GPUImageView`.

Extracted from the view alongside the other collaborators (``InputController``,
``OverlayPainter`` …) so the widget keeps GL lifecycle + Qt event plumbing while
the filmstrip navigation, reading-mode scrolling, pan clamping, and the
post-display fade hook live here. The controller holds no state of its own
beyond a back-reference to the view; the feature flags and caches stay on the
view because the renderers and overlay read them directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.gpu_image_view.filmstrip import (
    BAND_VPAD,
    ITEM_HEIGHT,
    ITEM_WIDTH,
    MINIMAP_GAP,
    compute_filmstrip_items,
    filmstrip_band,
    filmstrip_item_at,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class BrowseFeatures:
    """Filmstrip / reading-mode / pan-clamp / fade behaviour for the viewer."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view
        # Set transiently when paging backwards so the previous reading page
        # opens at its bottom (where the reader left off) rather than its top.
        self._anchor_bottom = False

    def reload_settings(self) -> None:
        """Re-read the browse feature flags from user settings.

        Called by the Preferences dialog so toggling the filmstrip / fade /
        smooth-navigation options takes effect on the live viewer without a
        restart (the view caches the flags at construction time).
        """
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        view = self._view
        view._filmstrip_enabled = bool(
            user_setting_dict.get("filmstrip_enabled", True))
        view._transition_enabled = bool(
            user_setting_dict.get("image_transition_enabled", True))
        view._smooth_nav_enabled = bool(
            user_setting_dict.get("smooth_navigation_enabled", False))
        view.update()

    # -- pan clamping -------------------------------------------------

    def clamp_pan(self) -> None:
        """Keep the zoomed image on screen — called after every pan / zoom.

        No-op while the image fits (it stays centred); once it overflows the
        canvas the offsets are held so neither edge can be dragged inside the
        viewport, so the image can never be lost off-screen.
        """
        view = self._view
        if not view.deep_zoom:
            return
        from Imervue.gpu_image_view.fit_view import canvas_size
        from Imervue.gpu_image_view.view_nav import clamp_pan_offset
        base = view.deep_zoom.levels[0]
        canvas_w, canvas_h = canvas_size(view)
        view.dz_offset_x = clamp_pan_offset(
            view.dz_offset_x, base.shape[1] * view.zoom, canvas_w)
        view.dz_offset_y = clamp_pan_offset(
            view.dz_offset_y, base.shape[0] * view.zoom, canvas_h)

    # -- reading mode -------------------------------------------------

    def reading_wheel(self, delta: float) -> None:
        """Reading-mode wheel: scroll the page, auto-advancing at the edges."""
        from Imervue.gpu_image_view.view_nav import reading_scroll
        view = self._view
        base = view.deep_zoom.levels[0]
        content_h = base.shape[0] * view.zoom
        new_off, advance = reading_scroll(
            view.dz_offset_y, content_h, view.height(), delta)
        view.dz_offset_y = new_off
        if advance > 0:
            from Imervue.gpu_image_view.actions.select import switch_to_next_image
            switch_to_next_image(main_gui=view)
        elif advance < 0:
            from Imervue.gpu_image_view.actions.select import switch_to_previous_image
            self._anchor_bottom = True  # open the previous page at its bottom
            switch_to_previous_image(main_gui=view)
        else:
            view.update()

    def apply_reading_fit(self) -> None:
        """Fit the current image to width, aligned to the top (or, when paging
        backwards, the bottom) for reading."""
        view = self._view
        if not view.deep_zoom:
            return
        view._fit_to_width()
        if self._anchor_bottom:
            from Imervue.gpu_image_view.view_nav import reading_bottom_offset
            content_h = view.deep_zoom.levels[0].shape[0] * view.zoom
            view.dz_offset_y = reading_bottom_offset(content_h, view.height())
        else:
            view.dz_offset_y = 0.0
        self._anchor_bottom = False
        self.clamp_pan()
        view.update()

    # -- post-display fade hook ---------------------------------------

    def begin_image_fade_in(self) -> None:
        """Post-display hook: in reading mode re-fit the new image to width/top,
        then fade it in (unless a slideshow already drives the opacity)."""
        view = self._view
        if view._reading_mode:
            self.apply_reading_fit()
        from Imervue.gpu_image_view.view_animator import should_transition
        slideshow = getattr(view, "_slideshow", None)
        running = bool(slideshow and slideshow.running)
        if should_transition(view._transition_enabled, running):
            view._image_fade.start()

    # -- filmstrip ----------------------------------------------------

    def filmstrip_strip_width(self) -> float:
        """Usable strip width — full width, minus the minimap so they don't overlap."""
        view = self._view
        rect = view._current_minimap_rect()
        if rect is None:
            return view.width()
        return max(float(ITEM_HEIGHT), rect[0] - MINIMAP_GAP)

    def filmstrip_items(self) -> list[tuple[int, float]]:
        """Visible ``(index, x_left)`` filmstrip items for the current state."""
        view = self._view
        return compute_filmstrip_items(
            enabled=view._filmstrip_enabled,
            in_grid_mode=view.tile_grid_mode,
            current_index=view.current_index,
            count=len(view.model.images),
            strip_width=self.filmstrip_strip_width(),
        )

    def filmstrip_item_at(self, pos) -> int | None:
        """Image index under a click *pos*, or None when outside the filmstrip."""
        view = self._view
        items = self.filmstrip_items()
        if not items:
            return None
        y_top, _ = filmstrip_band(view.height(), ITEM_HEIGHT, BAND_VPAD)
        return filmstrip_item_at(pos.x(), pos.y(), items, ITEM_WIDTH,
                                 y_top, view.height())

    def jump_to_filmstrip_index(self, index: int) -> None:
        """Open the image the user clicked in the filmstrip."""
        view = self._view
        images = view.model.images
        if not 0 <= index < len(images) or index == view.current_index:
            return
        view.current_index = index
        view.load_deep_zoom_image(images[index])

    def handle_deep_zoom_press(self, pos) -> bool:
        """Left-press in deep zoom: a filmstrip thumbnail jumps to that image;
        otherwise let the minimap claim the click. Returns True when consumed."""
        idx = self.filmstrip_item_at(pos)
        if idx is not None:
            self.jump_to_filmstrip_index(idx)
            return True
        return self._view._input.begin_minimap_nav(pos)
