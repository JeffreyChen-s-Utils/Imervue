"""The main window's image filter row.

The filename / extension / tag / date / rating filter row above the viewer,
applying it to the current folder while keeping the selected image where it
can, and saving and restoring its state. ``ImervueMainWindow`` mixes these
methods in.
"""
from __future__ import annotations

import contextlib
from datetime import date

from PySide6.QtWidgets import QWidget

from Imervue.gui.image_filter_bar import ImageFilterBar, filter_date
from Imervue.image.browser_state import ImageFilterSpec, filter_paths, refilter_keeping_current
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.best_effort import best_effort


def _any_tag_label() -> str:
    return language_wrapper.language_word_dict.get("image_filter_any_tag", "Any tag")


class MainWindowFilterMixin:
    """Image filter row of the main window."""

    def _build_filter_row(self) -> QWidget:
        """Build the filename/tag/rating/date filter bar above the viewer."""
        self._filter_bar = ImageFilterBar()
        self.image_filter = self._filter_bar.filename
        self.tag_filter = self._filter_bar.tag
        self.rating_filter = self._filter_bar.rating
        self.date_from_filter = self._filter_bar.date_from
        self.date_to_filter = self._filter_bar.date_to
        self.missing_batch_button = self._filter_bar.missing
        self._filter_bar.changed.connect(self._on_image_filter_changed)
        self._filter_bar.reset.clicked.connect(self._reset_image_filters)
        self.missing_batch_button.clicked.connect(self._show_missing_batch_menu)
        return self._filter_bar

    def _reset_image_filters(self) -> None:
        self._restore_filter_state({})
        self._on_image_filter_changed()
        self.image_filter.setFocus()

    def _update_filter_feedback(self) -> None:
        bar = getattr(self, "_filter_bar", None)
        if bar is not None:
            bar.update_feedback(active=any(self._filter_state().values()))

    def _on_viewer_filename_changed(self, name) -> None:
        base_template = language_wrapper.language_word_dict.get(
            "main_window_current_filename_format",
        ).format(name=name)
        # Append "(i/n)" position info when the viewer knows its
        # spot in the folder so the user can pace their browsing
        # without hunting through the file list. Keep the
        # baseline label so any locale that already localised
        # the prefix stays untouched.
        extras: list[str] = []
        with contextlib.suppress(AttributeError):   # no viewer / model yet during setup
            images = self.viewer.model.images or []
            idx = self.viewer.current_index
            if 0 <= idx < len(images):
                extras.append(f"({idx + 1}/{len(images)})")
        self.filename_label.setText(
            base_template + ("  " + " ".join(extras) if extras else ""),
        )
        self.filename_label.setToolTip(self.filename_label.text())
        self.exif_sidebar.schedule_update()
        # Keep the tab bar in lockstep with whatever image the viewer
        # now shows. Only sync in deep-zoom mode — tile grid / folder
        # browsing intentionally doesn't create tabs.
        with best_effort("sync the tab bar with the shown image"):
            images = self.viewer.model.images
            idx = self.viewer.current_index
            if self.viewer.deep_zoom and 0 <= idx < len(images):
                self._sync_current_tab_with_path(images[idx])

    def _on_image_filter_changed(self, *_args) -> None:
        if getattr(self, "_restoring_filter_controls", False):
            return
        self._update_filter_feedback()
        self._apply_image_filter()
        self._save_current_folder_session()

    def _apply_image_filter(self, text: str | None = None) -> None:
        """Filter the current folder by filename/tag/rating/date immediately."""
        from Imervue.gpu_image_view.actions.delete import pending_deleted_paths
        viewer = self.viewer
        base = list(getattr(viewer, "_unfiltered_images", None) or viewer.model.images)
        # Soft-deleted images linger in _unfiltered_images (the file is only
        # unlinked at shutdown); drop them so a filter change can't resurrect them.
        pending = pending_deleted_paths(getattr(viewer, "undo_stack", []))
        if pending:
            base = [p for p in base if p not in pending]
        if text is None:
            filtered = filter_paths(base, self._current_filter_spec(), self._image_metadata_index)
        else:
            filtered = self._filter_image_paths(base, text)
        current = viewer._current_path()
        if viewer.tile_grid_mode:
            from Imervue.gpu_image_view.tile_loader import sync_tile_grid_incremental
            sync_tile_grid_incremental(viewer, filtered)
            viewer.current_index = filtered.index(current) if current in filtered else 0
            self.refresh_list_view()
            viewer.update()
            return
        # In deep zoom / list mode: reconcile the shown image with the filter so a
        # filtered-out current image is dropped (not left as a phantom) and a
        # threshold cross re-fits — same handling as an external folder refresh.
        self._reconcile_deep_zoom_onto_list(
            filtered, getattr(viewer, "_deep_zoom_loading", None) or current,
            viewer.current_index,
        )

    def _reapply_filter_preserving_current(self) -> None:
        """Re-apply the active browse filter after opening a specific file.

        Opening a file (a Modify save's viewer reload, an image-tab switch)
        rebuilds the list from the whole folder via ``_open_file``, silently
        dropping the filter — the strip/list showed every image again. Re-filter
        the list, but keep the just-opened image current and visible even if it
        doesn't match, so the filter governs browsing without hiding what the
        user explicitly opened.
        """
        from Imervue.gpu_image_view.actions.delete import pending_deleted_paths
        viewer = self.viewer
        base = list(getattr(viewer, "_unfiltered_images", None) or viewer.model.images)
        pending = pending_deleted_paths(getattr(viewer, "undo_stack", []))
        base = [path for path in base if path not in pending]
        filtered = filter_paths(base, self._current_filter_spec(),
                                self._image_metadata_index)
        current = viewer._current_path()
        filtered = refilter_keeping_current(base, filtered, current)
        viewer.model.set_images(filtered)
        if current in filtered:
            viewer.current_index = filtered.index(current)
        self.refresh_list_view()
        viewer.update()

    def _current_filter_spec(self) -> ImageFilterSpec:
        tag = self._current_filter_tag()
        rating = ""
        if hasattr(self, "rating_filter"):
            rating = self.rating_filter.currentData() or ""
        start = self._parse_filter_date(
            self.date_from_filter.text() if hasattr(self, "date_from_filter") else "")
        end = self._parse_filter_date(
            self.date_to_filter.text() if hasattr(self, "date_to_filter") else "")
        if start and end and start > end:
            start = end = None
        return ImageFilterSpec(
            filename=self.image_filter.text() if hasattr(self, "image_filter") else "",
            tag=str(tag or ""),
            rating=str(rating or ""),
            date_from=start,
            date_to=end,
        )

    def _current_filter_tag(self) -> str:
        if not hasattr(self, "tag_filter"):
            return ""
        # Editable combos retain currentData() from the previously selected row.
        text = self.tag_filter.currentText()
        return "" if text == _any_tag_label() else text.strip()

    @staticmethod
    def _parse_filter_date(value: str) -> date | None:
        return filter_date(value or "")

    def _filter_state(self) -> dict:
        return {
            "filename": self.image_filter.text() if hasattr(self, "image_filter") else "",
            "tag": self._current_filter_tag(),
            "rating": self.rating_filter.currentData() if hasattr(self, "rating_filter") else "",
            "date_from": self.date_from_filter.text() if hasattr(self, "date_from_filter") else "",
            "date_to": self.date_to_filter.text() if hasattr(self, "date_to_filter") else "",
        }

    def _restore_filter_state(self, state: dict | None) -> None:
        if not state:
            state = {}
        self._restoring_filter_controls = True
        try:
            if hasattr(self, "image_filter"):
                self.image_filter.setText(str(state.get("filename") or ""))
            if hasattr(self, "tag_filter"):
                tag = str(state.get("tag") or "")
                idx = self.tag_filter.findData(tag)
                if idx >= 0:
                    self.tag_filter.setCurrentIndex(idx)
                else:
                    self.tag_filter.setEditText(tag)
            if hasattr(self, "rating_filter"):
                rating = str(state.get("rating") or "")
                idx = self.rating_filter.findData(rating)
                self.rating_filter.setCurrentIndex(max(idx, 0))
            if hasattr(self, "date_from_filter"):
                self.date_from_filter.setText(str(state.get("date_from") or ""))
            if hasattr(self, "date_to_filter"):
                self.date_to_filter.setText(str(state.get("date_to") or ""))
        finally:
            self._restoring_filter_controls = False
        self._update_filter_feedback()

    def _refresh_tag_filter_options(self) -> None:
        if not hasattr(self, "tag_filter"):
            return
        from Imervue.user_settings.tags import get_all_tags
        current = self._current_filter_tag()
        self._restoring_filter_controls = True
        try:
            self.tag_filter.clear()
            self.tag_filter.addItem(_any_tag_label(), "")
            for tag in sorted(get_all_tags()):
                self.tag_filter.addItem(tag, tag)
            idx = self.tag_filter.findData(current)
            if idx >= 0:
                self.tag_filter.setCurrentIndex(idx)
            elif current:
                self.tag_filter.setEditText(str(current))
        finally:
            self._restoring_filter_controls = False

    @staticmethod
    def _filter_image_paths(paths: list[str], query: str) -> list[str]:
        return filter_paths(paths, ImageFilterSpec(raw_query=query))
