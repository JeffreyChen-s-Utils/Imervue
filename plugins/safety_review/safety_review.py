"""
Safety Review — auto-detect and mosaic exposed genitalia.

Uses NudeNet to detect NSFW regions.  Only genitalia (male & female)
and anus are mosaiced; **nipples / breasts are never touched**.

Workflows
---------
* **Scan All** — one click to process every image in the current folder,
  overwriting originals.  A progress dialog tracks completion.
* **Single Quick Apply** — right-click in deep-zoom → applies to the
  current image immediately.
* **Batch (selected)** — tile-grid selection → batch dialog with output
  options.

Dependencies (auto-installed on first use):
  - nudenet
  - onnxruntime

This module is the plugin shell: a thin coordinator that wires the menu /
context-menu entries to the dialogs in :mod:`_dialogs`. The pure detection
core lives in :mod:`_detection`, the worker threads in :mod:`_workers`, and
the shared constants in :mod:`_constants`.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.system.app_paths import (
    frozen_site_packages as _frozen_site_packages,
    is_frozen as _is_frozen,
)

# Re-exported for backwards compatibility: external code and the test suite
# reference these symbols via ``safety_review.<name>``.
from safety_review._constants import (  # noqa: F401  (public re-export)
    ANIME_MOSAIC_CLASSES,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    MOSAIC_LABELS,
    _ERAX_MODEL,
    _ERAX_REPO,
    _ERAX_REVISION,
)
from safety_review._detection import (  # noqa: F401  (public re-export)
    _cached_anime_model,
    _find_external_python,
    _get_anime_model,
    _get_detector,
)
from safety_review._dialogs import (  # noqa: F401  (public re-export)
    BatchSafetyReviewDialog,
    SafetyReviewDialog,
    ScanAllDialog,
    _build_mode_row,
    _ensure_deps,
)
from safety_review._translations import _TRANSLATIONS

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.safety_review")


class SafetyReviewPlugin(ImervuePlugin):
    plugin_name = "Safety Review"
    plugin_version = "1.0.0"
    plugin_description = (
        "Auto-detect and mosaic exposed genitalia using NudeNet. "
        "Nipples are never mosaiced."
    )
    plugin_author = "Imervue"

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict

        # Try to reuse AI Tools submenu
        ai_menu = None
        for action in plugin_menu.actions():
            m = action.menu()
            if m and action.text().replace("&", "") == lang.get(
                    "bg_remove_menu", "AI Tools"):
                ai_menu = m
                break
        if ai_menu is None:
            ai_menu = plugin_menu.addMenu(
                lang.get("bg_remove_menu", "AI Tools"))

        ai_menu.addSeparator()

        # ★ Scan All — the primary action
        scan_all = ai_menu.addAction(
            lang.get("safety_review_scan_all",
                      "Safety Review — Scan All Images")
        )
        scan_all.triggered.connect(self._scan_all)

        # Single
        single = ai_menu.addAction(
            lang.get("safety_review_title",
                      "Safety Review — Auto Mosaic")
        )
        single.triggered.connect(self._open_single_dialog)

        # Batch
        batch = ai_menu.addAction(
            lang.get("safety_review_batch_title",
                      "Batch Safety Review")
        )
        batch.triggered.connect(self._open_batch_dialog)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        lang = language_wrapper.language_word_dict

        # Deep zoom — quick-apply on current image
        if viewer.deep_zoom:
            images = viewer.model.images
            if images and 0 <= viewer.current_index < len(images):
                path = images[viewer.current_index]
                action = menu.addAction(
                    lang.get("safety_review_quick",
                              "Safety Review — Quick Mosaic")
                )
                action.triggered.connect(lambda: self._quick_single(path))

        # Tile grid — batch on selection
        if (viewer.tile_grid_mode and viewer.tile_selection_mode
                and viewer.selected_tiles):
            paths = list(viewer.selected_tiles)
            action = menu.addAction(
                lang.get("safety_review_batch_title",
                          "Batch Safety Review")
            )
            action.triggered.connect(lambda: self._run_batch(paths))

        # Always show Scan All in context menu
        if viewer.model.images:
            action = menu.addAction(
                lang.get("safety_review_scan_all",
                          "Safety Review — Scan All Images")
            )
            action.triggered.connect(self._scan_all)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_frozen_env(self) -> tuple[str, str] | None:
        if not _is_frozen():
            return None
        python = _find_external_python()
        if not python:
            logger.error("No external Python for subprocess")
            return None
        return python, str(_frozen_site_packages())

    def _scan_all(self):
        """Open the scan-all dialog — user picks folder and settings."""
        initial = list(self.viewer.model.images) if self.viewer.model.images else None
        try:
            dlg = ScanAllDialog(
                self.viewer, initial_paths=initial,
                get_frozen_env=self._get_frozen_env)
            dlg.exec()
        except Exception:
            logger.error("Scan-all dialog failed", exc_info=True)

    def _quick_single(self, path: str):
        """Right-click quick apply — opens single-image dialog."""
        if not Path(path).is_file():
            return
        self._run_single(path)

    def _open_single_dialog(self):
        images = self.viewer.model.images
        if not images or self.viewer.current_index >= len(images):
            return
        path = images[self.viewer.current_index]
        self._run_single(path)

    def _run_single(self, path: str):
        if not Path(path).is_file():
            return
        try:
            dlg = SafetyReviewDialog(
                self.viewer, path,
                get_frozen_env=self._get_frozen_env)
            dlg.exec()
        except Exception:
            logger.error("Single dialog failed", exc_info=True)

    def _open_batch_dialog(self):
        if (self.viewer.tile_grid_mode and self.viewer.tile_selection_mode
                and self.viewer.selected_tiles):
            paths = list(self.viewer.selected_tiles)
        else:
            paths = list(self.viewer.model.images)
        if paths:
            self._run_batch(paths)

    def _run_batch(self, paths: list[str]):
        try:
            dlg = BatchSafetyReviewDialog(
                self.viewer, paths,
                get_frozen_env=self._get_frozen_env)
            dlg.exec()
        except Exception:
            logger.error("Batch dialog failed", exc_info=True)

    # ------------------------------------------------------------------
    # Translations
    # ------------------------------------------------------------------

    def get_translations(self) -> dict[str, dict[str, str]]:
        return _TRANSLATIONS
