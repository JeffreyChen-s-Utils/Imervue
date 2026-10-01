"""Browse modes of the main window.

Switching between the thumbnail wall and the list view, activating an image
from the list, returning from deep zoom, and the tile size / padding
settings. ``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

from Imervue.user_settings.user_setting_dict import user_setting_dict


class MainWindowBrowseMixin:
    """Browse modes of the main window."""

    def is_list_mode(self) -> bool:
        return self._browse_mode == "list"

    def set_browse_mode(self, mode: str) -> None:
        """Switch between tile grid (mode='grid') and the QTableView list."""
        if mode not in ("grid", "list"):
            return
        if mode == self._browse_mode:
            return
        self._browse_mode = mode
        if mode == "list":
            # Sync list view with whatever the viewer currently knows about
            self.refresh_list_view()
            self._view_stack.setCurrentIndex(1)
        else:
            self._view_stack.setCurrentIndex(0)
            # If viewer was sitting on tile grid, re-render it fresh. The wall
            # renders straight from the tile cache with no per-tile lazy refill,
            # so reload it whenever the cache no longer covers the folder
            # (otherwise it would show blank placeholders).
            if self.viewer.model.images and not self.viewer.deep_zoom:
                from Imervue.gpu_image_view.tile_loader import tile_grid_needs_reload
                if tile_grid_needs_reload(self.viewer.tile_cache, self.viewer.model.images):
                    self.viewer.load_tile_grid_async(list(self.viewer.model.images))
                else:
                    self.viewer.tile_grid_mode = True
                    self.viewer.update()

        # Sync View menu radio buttons with the current mode
        grid_action = getattr(self, "_mode_action_grid", None)
        list_action = getattr(self, "_mode_action_list", None)
        if grid_action is not None:
            grid_action.setChecked(mode == "grid")
        if list_action is not None:
            list_action.setChecked(mode == "list")

    def toggle_browse_mode(self) -> None:
        self.set_browse_mode("list" if self._browse_mode == "grid" else "grid")

    def refresh_list_view(self) -> None:
        """Populate the list view from the viewer's current image list."""
        self.image_list_view.set_paths(
            list(self.viewer.model.images),
            metadata_index=getattr(self, "_image_metadata_index", None),
        )

    def refetch_list_rows(self, paths) -> None:
        """Have the list view read *paths* again: they were rewritten, removed or restored."""
        self.image_list_view.refetch(paths)

    def delete_list_selection(self, paths: list[str]) -> None:
        """Delete the list's selected rows as Delete does on the wall: undoable, trashed later."""
        from Imervue.gpu_image_view.actions import delete
        self.viewer.selected_tiles.clear()
        self.viewer.selected_tiles.update(paths)
        delete.delete_selected_tiles(self.viewer)
        self.refresh_list_view()

    def mark_list_selection(self, action: str, paths: list[str]) -> None:
        """Rate, favourite, cull-flag or colour-label the list's selected rows, as on the wall."""
        from Imervue.gpu_image_view.actions.keyboard_actions import (
            rate_current_image,
            toggle_favorite,
        )
        from Imervue.gpu_image_view.cull_actions import apply_color_label, apply_cull_state
        from Imervue.gpu_image_view.key_action_dispatcher import cull_state_for
        viewer = self.viewer
        if action.startswith("rate_"):
            rate_current_image(viewer, int(action[-1]), targets=paths)
        elif action == "favorite":
            toggle_favorite(viewer, targets=paths)
        elif action.startswith("label_"):
            apply_color_label(viewer, action.removeprefix("label_"), targets=paths)
        elif cull_state_for(action) is not None:
            apply_cull_state(viewer, cull_state_for(action), targets=paths)
        self.image_list_view.viewport().update()   # the Rating and Label columns

    def escape_from_list(self) -> None:
        """Esc in the list: leave fullscreen first, else go back to the thumbnail wall."""
        if self.isFullScreen():
            from Imervue.gpu_image_view.actions.keyboard_actions import toggle_fullscreen
            toggle_fullscreen(self.viewer)
            return
        self.set_browse_mode("grid")

    def undo_from_list(self) -> None:
        """The viewer's undo (the last edit, else the last delete), then show what came back."""
        self.viewer.run_shortcut_action("undo")
        self.refresh_list_view()

    def _on_list_activated(self, path: str) -> None:
        """Double-clicking a row opens that image in the deep-zoom viewer.

        We swap the stack back to the viewer so deep zoom is visible; Esc
        from deep zoom takes the user back to the list because
        ``_browse_mode`` is still ``"list"``.
        """
        if not path:
            return
        images = self.viewer.model.images
        # A list row can outlive its image by a frame — a refresh dropped it
        # from the model but the table hasn't repopulated yet. Activating the
        # stale row would leave the list for a load the completion guard then
        # discards, stranding a stuck "Loading…" view. Ignore it and stay put.
        if path not in images:
            return
        self.viewer.current_index = images.index(path)
        self._view_stack.setCurrentIndex(0)
        self.viewer.tile_grid_mode = False
        self.viewer.load_deep_zoom_image(path)

    def after_deep_zoom_escape(self) -> None:
        """Called by the viewer after Esc leaves deep zoom.

        If the user was browsing in list mode, restore the list view instead
        of the tile grid.
        """
        if self._browse_mode == "list":
            self._view_stack.setCurrentIndex(1)

    def change_tile_size(self, size):
        # Delegate to the viewer, which keeps the user in deep zoom (instead of
        # dropping back to the wall and wiping the status bar) when a size is
        # picked mid-zoom. See ``GPUImageView.set_thumbnail_size``.
        self.viewer.set_thumbnail_size(size)

    def change_tile_padding(self, padding: int) -> None:
        """Set thumbnail-grid padding and persist — 0 compact, 8 standard, 16 relaxed."""
        padding = int(max(0, min(64, padding)))
        self.viewer.tile_padding = padding
        user_setting_dict["tile_padding"] = padding
        if self.viewer.tile_grid_mode:
            self.viewer.update()
