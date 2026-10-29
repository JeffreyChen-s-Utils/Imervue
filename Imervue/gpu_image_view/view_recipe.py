"""Modify-panel binding and recipe reloads of the viewer.

Mixed into :class:`GPUImageView`: opening the Modify tab on the current
image, pushing committed recipes onto the undo stack, and re-decoding the
shown image after a recipe or colour-vision view-mode change.
"""
from __future__ import annotations


class ViewRecipeMixin:
    """Modify panel and recipe reload for :class:`GPUImageView`."""

    # ===========================
    # Modify panel (non-destructive editing)
    # ===========================

    @property
    def _develop_panel(self):
        """Access the modify panel from the main window (may be None in tests)."""
        return getattr(self.main_window, "modify_panel", None)

    def open_develop_panel(self):
        """Switch to the Modify tab in the main QTabWidget and bind."""
        panel = self._develop_panel
        if panel is None:
            return
        images = self.model.images
        path = None
        if images and 0 <= self.current_index < len(images):
            path = images[self.current_index]
        panel.bind_to_path(path)
        # Switch to the Modify tab (index 1) in the main QTabWidget.
        main_tabs = getattr(self.main_window, "_main_tabs", None)
        if main_tabs is not None and main_tabs.count() > 1:
            main_tabs.setCurrentIndex(1)

    def _on_recipe_committed(self, path, old_recipe, new_recipe):
        """Panel committed a new recipe — push undo command + reload."""
        from Imervue.gpu_image_view.actions.recipe_commands import EditRecipeCommand
        cmd = EditRecipeCommand(self, path, old_recipe, new_recipe)
        self.undo_manager.push(cmd)

    def set_cvd_view_mode(self, mode: str | None) -> None:
        """Toggle the colour-vision-deficiency view mode and reload
        the current image so the change is immediately visible.

        The entire prefetch cache is dropped — every cached frame
        was rendered against the *previous* CVD mode and would
        flash the wrong colours when the user pages through it."""
        from Imervue.gpu_image_view.cvd_view_mode import set_view_mode
        set_view_mode(mode)
        # Burn the prefetch cache + cancel inflight workers; the
        # next paint reloads against the new mode.
        self._cancel_all_prefetch()
        self.reload_current_image_with_recipe()

    def reload_current_image_with_recipe(self, path: str | None = None):
        """Drop any cached baked pixels for ``path`` and reload it fresh.

        Called by EditRecipeCommand after it updates the recipe in the
        store. If ``path`` is None, reloads whatever's currently showing.
        """
        if path is None:
            images = self.model.images
            if not images or self.current_index >= len(images):
                return
            path = images[self.current_index]
        # Any prefetched baked tiles for this path are stale — drop them.
        self._prefetch.discard(path)
        # Force a fresh load — _clear_deep_zoom + load_deep_zoom_image will
        # ask recipe_store for the new recipe and apply it.
        if self.model.images and 0 <= self.current_index < len(self.model.images) \
                and self.model.images[self.current_index] == path:
            # Save the live zoom/pan first: _clear_deep_zoom nulls _deep_zoom_path,
            # so load_deep_zoom_image's own save would no-op and a tonal recipe
            # edit would snap the view back to the entry zoom.
            self._save_view_state()
            self._cancel_deep_zoom_worker()
            self._clear_deep_zoom()
            self.load_deep_zoom_image(path)
            # Re-bind the develop panel so slider labels reflect the new recipe.
            if self._develop_panel is not None and self._develop_panel.isVisible():
                self._develop_panel.bind_to_path(path)
