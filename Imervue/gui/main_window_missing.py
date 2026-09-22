"""Missing-file handling of the main window.

When library entries point at files that no longer exist: the batch menu that
auto-matches them by name, removes them, or relocates a whole root folder,
and the migration of per-path metadata (tags, ratings, recipes) to the new
paths. ``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QMenu

from Imervue.image.browser_state import (
    auto_match_same_name,
    migrate_view_path_state,
    missing_paths,
    relocate_root,
    remove_missing,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict


class MainWindowMissingMixin:
    """Missing-file handling of the main window."""

    def _show_missing_batch_menu(self) -> None:
        if not hasattr(self, "missing_batch_button"):
            return
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        scan_action = menu.addAction(
            lang.get("missing_batch_scan_same_name", "Auto-match same-name files"),
        )
        remove_action = menu.addAction(
            lang.get("missing_batch_remove", "Remove missing from view"),
        )
        relocate_action = menu.addAction(
            lang.get("missing_batch_relocate_root", "Relocate root folder..."),
        )
        chosen = menu.exec(self.missing_batch_button.mapToGlobal(
            self.missing_batch_button.rect().bottomLeft(),
        ))
        if chosen is scan_action:
            self._batch_auto_match_missing()
        elif chosen is remove_action:
            self._batch_remove_missing()
        elif chosen is relocate_action:
            self._batch_relocate_root()

    def _missing_candidates(self) -> list[str]:
        paths = []
        paths.extend(getattr(self.viewer, "_unfiltered_images", []) or [])
        paths.extend(getattr(getattr(self.viewer, "model", None), "images", []) or [])
        if getattr(self.viewer, "_deep_zoom_error", None):
            paths.append(self.viewer._deep_zoom_error[0])
        seen = set()
        unique = []
        for path in paths:
            if path and path not in seen:
                seen.add(path)
                unique.append(path)
        return missing_paths(unique)

    def _batch_auto_match_missing(self) -> None:
        folder = self._current_view_folder()
        mapping = auto_match_same_name(self._missing_candidates(), folder)
        self._apply_missing_replacements(mapping)

    def _batch_remove_missing(self) -> None:
        base = list(getattr(self.viewer, "_unfiltered_images", None) or self.viewer.model.images)
        kept = remove_missing(base)
        removed = len(base) - len(kept)
        self.viewer._unfiltered_images = kept
        offline = getattr(self.viewer, "offline_paths", None)
        if isinstance(offline, set):
            offline.intersection_update(set(kept))
        if hasattr(self.viewer, "tile_errors"):
            self.viewer.tile_errors = {
                path: msg for path, msg in getattr(self.viewer, "tile_errors", {}).items()
                if path in kept
            }
        self._apply_image_filter()
        self._toast_missing_result("missing_batch_removed_done", removed)

    def _batch_relocate_root(self) -> None:
        missing = self._missing_candidates()
        if not missing:
            self._toast_missing_result("missing_batch_none", 0)
            return
        from PySide6.QtWidgets import QFileDialog
        lang = language_wrapper.language_word_dict
        new_root = QFileDialog.getExistingDirectory(
            self,
            lang.get("missing_batch_relocate_root", "Relocate root folder..."),
            str(Path(missing[0]).parent),
        )
        if not new_root:
            return
        old_root = self._common_missing_root(missing)
        self._apply_missing_replacements(relocate_root(missing, old_root, new_root))

    @staticmethod
    def _common_missing_root(paths: list[str]) -> str:
        parents = [str(Path(path).parent) for path in paths]
        try:
            return os.path.commonpath(parents)
        except ValueError:
            return parents[0] if parents else ""

    def _apply_missing_replacements(self, mapping: dict[str, str]) -> None:
        if not mapping:
            self._toast_missing_result("missing_batch_none", 0)
            return
        viewer = self.viewer
        migrate_view_path_state(viewer, mapping)
        for old, new in mapping.items():
            self._image_metadata_index.move(old, new)
            self._migrate_user_path_metadata(old, new)
        for attr in ("_unfiltered_images",):
            paths = list(getattr(viewer, attr, []) or [])
            setattr(viewer, attr, [mapping.get(path, path) for path in paths])
        if getattr(viewer, "model", None) is not None:
            viewer.model.set_images([mapping.get(path, path) for path in viewer.model.images])
        if getattr(viewer, "_deep_zoom_error", None):
            old_path, _ = viewer._deep_zoom_error
            if old_path in mapping:
                viewer._deep_zoom_error = None
                viewer.load_deep_zoom_image(mapping[old_path])
        self._apply_image_filter()
        self._toast_missing_result("missing_batch_relinked_done", len(mapping))

    @staticmethod
    def _migrate_user_path_metadata(old_path: str, new_path: str) -> None:
        ratings = user_setting_dict.get("image_ratings")
        if isinstance(ratings, dict) and old_path in ratings and new_path not in ratings:
            ratings[new_path] = ratings.pop(old_path)
        tags = user_setting_dict.get("image_tags")
        if isinstance(tags, dict):
            for paths in tags.values():
                if isinstance(paths, list) and old_path in paths and new_path not in paths:
                    paths[paths.index(old_path)] = new_path

    def _toast_missing_result(self, key: str, count: int) -> None:
        if not hasattr(self, "toast"):
            return
        lang = language_wrapper.language_word_dict
        fallback = {
            "missing_batch_none": "No missing files matched",
            "missing_batch_removed_done": "Removed {n} missing file(s)",
            "missing_batch_relinked_done": "Relinked {n} missing file(s)",
        }.get(key, "{n}")
        msg = lang.get(key, fallback).format(n=count)
        if count:
            self.toast.success(msg)
        else:
            self.toast.info(msg)

    def record_image_issue(self, path: str, message: str) -> None:
        panel = getattr(self, "image_issue_panel", None)
        if panel is not None:
            panel.add_issue(path, message)

    def clear_image_issue(self, path: str) -> None:
        panel = getattr(self, "image_issue_panel", None)
        if panel is not None:
            panel.clear_issue(path)
