"""Status bar of the main window.

Transient messages, the progress bar for long folder scans, and the image
info label (file name, size, zoom, index) kept in step with the viewer.
``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations


from Imervue.multi_language.language_wrapper import language_wrapper


class MainWindowStatusMixin:
    """Status bar of the main window."""

    def set_status(self, text: str):
        self._progress_hide_timer.stop()
        if self._progress_bar.maximum() > 0 and (
            self._progress_bar.value() >= self._progress_bar.maximum()
        ):
            self._progress_bar.setVisible(False)
        self._status_label.setText(text)

    def show_progress(self, current: int, total: int):
        self._progress_hide_timer.stop()
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "status_loading_progress", "Loading {current}/{total}..."
            ).format(current=current, total=total)
        )
        if total > 0 and current >= total:
            self._progress_hide_timer.start()

    def _hide_progress(self):
        self._progress_bar.setVisible(False)
        self._status_label.setText(
            language_wrapper.language_word_dict.get("status_ready", "Ready")
        )

    def update_status_info(
            self,
            *,
            index: str | None = None,
            resolution: str | None = None,
            size: str | None = None,
            zoom: str | None = None,
            cursor: str | None = None,
            label: str | None = None,
    ) -> None:
        """Update any subset of the permanent info slots in the status bar.

        Called by the viewer whenever the shown image, zoom level, or mouse
        position changes. Passing ``None`` leaves a slot untouched; passing
        an empty string clears it.
        """
        if index is not None:
            self._status_info_index.setText(index)
        if resolution is not None:
            self._status_info_resolution.setText(resolution)
        if size is not None:
            self._status_info_size.setText(size)
        if zoom is not None:
            self._status_info_zoom.setText(zoom)
        if cursor is not None:
            self._status_info_cursor.setText(cursor)
        if label is not None:
            self._apply_status_label(label)

    def _apply_status_label(self, color: str) -> None:
        """Render the colour-label chip as a coloured pill, or hide when empty."""
        from Imervue.user_settings.color_labels import COLOR_RGB
        if not color:
            self._status_info_label.setText("")
            self._status_info_label.setStyleSheet(
                "padding: 0 8px; border-radius: 3px;"
            )
            return
        rgb = COLOR_RGB.get(color)
        if rgb is None:
            self._status_info_label.setText("")
            return
        r, g, b = rgb
        display = language_wrapper.language_word_dict.get(
            f"color_label_{color}", color.title()
        )
        self._status_info_label.setText(display)
        self._status_info_label.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: white;"
            " padding: 0 8px; border-radius: 3px; font-weight: bold;"
        )

    def clear_status_info(self) -> None:
        """Wipe all permanent info slots — used when leaving an image."""
        self.update_status_info(
            index="", resolution="", size="", zoom="", cursor="", label="",
        )

    def _collect_memory_pressure(self) -> dict:
        """Source callable for the status-bar memory-pressure widget.
        Returns the current ``(used, limit)`` byte counts plus a few
        cache-population numbers for the tooltip. Returns zeros when
        the viewer isn't ready yet so the widget shows ``--``."""
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return {"used_bytes": 0, "limit_bytes": 0}
        return {
            "used_bytes": int(getattr(viewer, "_vram_usage", 0)),
            "limit_bytes": int(getattr(viewer, "_vram_limit", 0)),
            "tile_count": len(getattr(viewer, "tile_textures", {})),
            "prefetch_count": len(getattr(viewer, "_prefetch_cache", {})),
        }

    def _on_memory_pressure_clear(self) -> None:
        """Click handler for the indicator. Drops the prefetch cache
        and the tile-texture cache so the user can recover the
        budget without restarting the app."""
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return
        cancel = getattr(viewer, "_cancel_all_prefetch", None)
        if callable(cancel):
            cancel()
        clear_tiles = getattr(viewer, "_delete_all_tile_textures", None)
        if callable(clear_tiles):
            clear_tiles()
        tile_cache = getattr(viewer, "tile_cache", None)
        if isinstance(tile_cache, dict):
            tile_cache.clear()
