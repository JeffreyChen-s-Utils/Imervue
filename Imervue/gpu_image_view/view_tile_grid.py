"""Thumbnail-wall loading of the viewer.

Mixed into :class:`GPUImageView`: thumbnail-size changes, the tile-loader
entry points and worker callbacks, the hover preview and the wall scroll
clamp. The loading itself lives in ``tile_loader``.
"""
from __future__ import annotations

from Imervue.gpu_image_view.tile_layout import plan_tile_size_change


class ViewTileGridMixin:
    """Thumbnail-wall loading for :class:`GPUImageView`."""

    # ---------------------------
    # Tile Grid 載入
    # ---------------------------
    def set_thumbnail_size(self, size) -> None:
        """Apply a new thumbnail size picked from the menu.

        While in deep zoom the grid is *not* rebuilt — that would drop the
        user back to the wall and wipe the status-bar info. The size is stored
        and the grid is regenerated lazily on the next exit to the wall.
        """
        self.thumbnail_size = None if size == "None" else size
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["thumbnail_size"] = self.thumbnail_size
        in_deep_zoom = self.deep_zoom is not None and not self.tile_grid_mode
        action = plan_tile_size_change(
            in_deep_zoom=in_deep_zoom, has_images=bool(self.model.images),
        )
        if action == "rebuild":
            self.clear_tile_grid()
            self.load_tile_grid_async(image_paths=self.model.images)
        elif action == "defer":
            self._tile_size_dirty = True
            self.update()

    def load_tile_grid_async(self, image_paths):
        """Load a folder's thumbnails — public entry point. External contract."""
        from Imervue.gpu_image_view.tile_loader import load_tile_grid_async
        load_tile_grid_async(self, image_paths)

    def _on_thumbnail_loaded(self, img_data, path, generation):
        from Imervue.gpu_image_view.tile_loader import on_thumbnail_loaded
        on_thumbnail_loaded(self, img_data, path, generation)

    def _on_thumbnail_error(self, path, message, generation):
        from Imervue.gpu_image_view.tile_loader import on_thumbnail_error
        on_thumbnail_error(self, path, message, generation)

    def _flush_thumbnail_progress(self) -> None:
        """Coalesced status-bar update — connected to the progress coalescer."""
        from Imervue.gpu_image_view.tile_loader import flush_thumbnail_progress
        flush_thumbnail_progress(self)

    def _tick_offline_sweep(self) -> None:
        """Timer tick: refresh ``offline_paths`` via a background stat sweep."""
        from Imervue.gpu_image_view.tile_loader import tick_offline_sweep
        tick_offline_sweep(self)

    def _on_offline_scan_finished(self, missing, generation, rewritten=()) -> None:
        from Imervue.gpu_image_view.tile_loader import on_offline_scan_finished
        on_offline_scan_finished(self, missing, generation, rewritten)

    def _reload_rewritten_image(self, path: str) -> None:
        """Show *path* again, thumbnail and list row too: another program saved over it."""
        from Imervue.gpu_image_view.tile_loader import refetch_list_rows, refresh_rewritten_tile
        refresh_rewritten_tile(self, path, self._load_generation)
        refetch_list_rows(self, (path,))
        self.reload_current_image_with_recipe(path)

    # 保持向後相容（undo_delete 使用）
    def add_thumbnail(self, img_data, path, generation=None):
        """Insert a thumbnail directly — external contract (undo_delete)."""
        from Imervue.gpu_image_view.tile_loader import add_thumbnail
        add_thumbnail(self, img_data, path, generation)

    def _ensure_filmstrip_thumbnail(self, path: str) -> None:
        """Lazily decode *path* into ``tile_cache`` for the filmstrip / preview.

        Called from the overlay paint path when a needed thumbnail is missing
        so the filmstrip and deep-zoom loading preview self-heal regardless of
        how the cache went cold (open-file, folder refresh while zoomed)."""
        from Imervue.gpu_image_view.tile_loader import ensure_filmstrip_thumbnail
        ensure_filmstrip_thumbnail(self, path)

    def _on_filmstrip_thumbnail_loaded(self, img_data, path, generation) -> None:
        """Worker callback for a lazily-requested filmstrip thumbnail."""
        from Imervue.gpu_image_view.tile_loader import on_filmstrip_thumbnail_loaded
        on_filmstrip_thumbnail_loaded(self, img_data, path, generation)

    # ---------------------------
    # Hover preview
    # ---------------------------
    def _update_hover_preview(self, event) -> None:
        """Arm the tile hover popup — called by the input controller."""
        from Imervue.gpu_image_view.hover_preview_binding import update_hover_preview
        update_hover_preview(self, event)

    def _cancel_hover_preview(self) -> None:
        from Imervue.gpu_image_view.hover_preview_binding import cancel_hover_preview
        cancel_hover_preview(self)

    def _clamp_grid_scroll(self) -> None:
        """Hold the thumbnail-wall scroll within its content so the wheel /
        middle-drag can't flick the grid into empty space above the first row
        or below the last. Recomputes the live layout (cols / cell depend on
        the widget width, thumbnail size and DPR) so the bound always matches
        what the renderer draws this frame."""
        from Imervue.gpu_image_view.tile_layout import (
            clamp_grid_offset,
            tile_grid_layout,
        )
        base_tile = self._tile_renderer.base_size()
        draw_scale, cell, cols = tile_grid_layout(
            self.width(), base_tile, self.tile_scale,
            self.tile_padding, self.devicePixelRatio(),
        )
        self.grid_offset_y = clamp_grid_offset(
            self.grid_offset_y, len(self.model.images), cols, cell,
            base_tile * draw_scale, self.height(),
        )
