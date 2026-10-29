"""
AI \u53bb\u80cc\u63d2\u4ef6
AI Background Remover \u2014 remove image backgrounds using rembg (U2-Net).

Dependencies are auto-installed on first use via the main app's pip installer.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu

from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.app_paths import is_frozen as _is_frozen

# The workers, dialogs and paths live in sibling modules; they are re-exported
# here because this module stays the plugin's public import location.
from ai_background_remover.ai_background_remover_workers import (
    _MODELS_DIR,
    _PLUGIN_DIR,
    _RUNNER_SCRIPT,
    _BatchRemoveWorker,
    _RemoveBackgroundWorker,
    _SubprocessBatchWorker,
    _SubprocessRemoveWorker,
)
from ai_background_remover.ai_background_remover_dialogs import (
    MODEL_DESCRIPTIONS,
    MODELS,
    BatchRemoveBackgroundDialog,
    RemoveBackgroundDialog,
)

__all__ = [
    "MODELS",
    "MODEL_DESCRIPTIONS",
    "REQUIRED_PACKAGES",
    "AIBackgroundRemoverPlugin",
    "BatchRemoveBackgroundDialog",
    "RemoveBackgroundDialog",
    "_BatchRemoveWorker",
    "_MODELS_DIR",
    "_PLUGIN_DIR",
    "_RUNNER_SCRIPT",
    "_RemoveBackgroundWorker",
    "_SubprocessBatchWorker",
    "_SubprocessRemoveWorker",
    "_ensure_deps",
    "_find_external_python",
]

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_bg_remover")
# NOTE: no logging.basicConfig here. Reconfiguring the ROOT logger at import time
# hijacked all propagated logging into a truncated CWD file, and constructing the
# FileHandler raised (aborting plugin load) when the CWD was read-only (a frozen
# install under Program Files). Use the named module logger above instead.

# Frozen \u74b0\u5883 DLL \u8def\u5f91\u8a2d\u5b9a\uff08\u50c5\u4f9b\u975e subprocess \u6a21\u5f0f\u4f7f\u7528\uff09
if _is_frozen():
    logger.info("AI BG Remover: frozen env detected")
    try:
        from Imervue.system.app_paths import app_dir as _app_dir
        _site_packages = _app_dir() / "lib" / "site-packages"
        logger.info("AI BG Remover: site-packages = %s, exists=%s",
                     _site_packages, _site_packages.is_dir())
    except Exception:
        logger.error("AI BG Remover: frozen env setup failed", exc_info=True)

# ===========================
# \u5957\u4ef6\u9700\u6c42
# ===========================

REQUIRED_PACKAGES = [
    ("rembg", "rembg"),
    ("onnxruntime", "onnxruntime"),
]


# ===========================
# Python \u641c\u5c0b\uff08\u51cd\u7d50\u74b0\u5883\u7528\uff09
# ===========================

def _find_external_python() -> str | None:
    """Find the external Python used by pip_installer (cached)."""
    from Imervue.plugin.pip_installer import _find_python
    return _find_python()


# ===========================
# Plugin \u672c\u9ad4
# ===========================

def _ensure_deps(parent, on_ready):
    logger.info("_ensure_deps called")
    try:
        ensure_dependencies(parent, REQUIRED_PACKAGES, on_ready)
        logger.info("_ensure_deps: ensure_dependencies returned (async started)")
    except Exception:
        logger.error("_ensure_deps: ensure_dependencies raised", exc_info=True)


class AIBackgroundRemoverPlugin(ImervuePlugin):
    plugin_name = "AI Background Remover"
    plugin_version = "1.2.0"
    plugin_description = "Remove image backgrounds using AI (rembg / U2-Net)"
    plugin_author = "Imervue"

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict
        self._menu = plugin_menu.addMenu(lang.get("bg_remove_menu", "AI Tools"))

        action = self._menu.addAction(lang.get("bg_remove_title", "AI Background Removal"))
        action.triggered.connect(self._open_single_dialog)

        batch_action = self._menu.addAction(
            lang.get("bg_remove_batch_title", "Batch AI Background Removal")
        )
        batch_action.triggered.connect(self._open_batch_dialog)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        lang = language_wrapper.language_word_dict

        if viewer.deep_zoom:
            images = viewer.model.images
            if images and 0 <= viewer.current_index < len(images):
                path = images[viewer.current_index]
                action = menu.addAction(lang.get("bg_remove_title", "AI Background Removal"))
                action.triggered.connect(lambda: self._remove_single(path))

        if (viewer.tile_grid_mode and viewer.tile_selection_mode
                and viewer.selected_tiles and len(viewer.selected_tiles) >= 1):
            paths = list(viewer.selected_tiles)
            action = menu.addAction(
                lang.get("bg_remove_batch_title", "Batch AI Background Removal")
            )
            action.triggered.connect(lambda: self._remove_batch(paths))

    def _get_frozen_env(self) -> tuple[str, str] | None:
        """In frozen mode, find external Python and site-packages path.

        Returns (python_path, site_packages_path) or None in dev mode.
        """
        if not _is_frozen():
            return None
        python = _find_external_python()
        if not python:
            logger.error("No external Python found for subprocess")
            return None
        from Imervue.system.app_paths import app_dir
        site_pkgs = str(app_dir() / "lib" / "site-packages")
        logger.info("Frozen env: python=%s, site_packages=%s", python, site_pkgs)
        return python, site_pkgs

    def _open_single_dialog(self):
        images = self.viewer.model.images
        if not images or self.viewer.current_index >= len(images):
            return
        path = images[self.viewer.current_index]
        self._remove_single(path)

    def _remove_single(self, path: str):
        logger.info("_remove_single called, path=%s", path)
        if not Path(path).is_file():
            return

        def _on_ready():
            logger.info("_remove_single on_ready fired")
            try:
                env = self._get_frozen_env()
                dlg = RemoveBackgroundDialog(self.viewer, path, frozen_env=env)
                logger.info("_remove_single: dialog created, calling exec()")
                dlg.exec()
                logger.info("_remove_single: dialog exec() returned")
            except Exception:
                logger.error("_remove_single: failed", exc_info=True)

        _ensure_deps(self.main_window, _on_ready)

    def _open_batch_dialog(self):
        if (self.viewer.tile_grid_mode and self.viewer.tile_selection_mode
                and self.viewer.selected_tiles):
            paths = list(self.viewer.selected_tiles)
        else:
            paths = list(self.viewer.model.images)
        if paths:
            self._remove_batch(paths)

    def _remove_batch(self, paths: list[str]):
        logger.info("_remove_batch called, %d paths", len(paths))

        def _on_ready():
            logger.info("_remove_batch on_ready fired")
            try:
                env = self._get_frozen_env()
                dlg = BatchRemoveBackgroundDialog(self.viewer, paths, frozen_env=env)
                logger.info("_remove_batch: dialog created, calling exec()")
                dlg.exec()
                logger.info("_remove_batch: dialog exec() returned")
            except Exception:
                logger.error("_remove_batch: failed", exc_info=True)

        _ensure_deps(self.main_window, _on_ready)

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "bg_remove_menu": "AI Tools",
                "bg_remove_title": "AI Background Removal",
                "bg_remove_batch_title": "Batch AI Background Removal",
                "bg_remove_source": "Source:",
                "bg_remove_model": "Model:",
                "bg_remove_alpha_matting": "Alpha matting (smoother edges, slower)",
                "bg_remove_run": "Remove Background",
                "bg_remove_done": "Done! Saved to: {path}",
                "bg_remove_done_short": "Background removed!",
                "bg_remove_batch_done": "Processed {success}/{total} image(s)",
            },
            "Traditional_Chinese": {
                "bg_remove_menu": "AI \u5de5\u5177",
                "bg_remove_title": "AI \u53bb\u80cc",
                "bg_remove_batch_title": "\u6279\u6b21 AI \u53bb\u80cc",
                "bg_remove_source": "\u4f86\u6e90\uff1a",
                "bg_remove_model": "\u6a21\u578b\uff1a",
                "bg_remove_alpha_matting": "Alpha matting\uff08\u908a\u7de3\u66f4\u5e73\u6ed1\uff0c\u8f03\u6162\uff09",
                "bg_remove_run": "\u53bb\u9664\u80cc\u666f",
                "bg_remove_done": "\u5b8c\u6210\uff01\u5df2\u5132\u5b58\u81f3\uff1a{path}",
                "bg_remove_done_short": "\u53bb\u80cc\u5b8c\u6210\uff01",
                "bg_remove_batch_done": "\u5df2\u8655\u7406 {success}/{total} \u5f35\u5716\u7247",
            },
            "Chinese": {
                "bg_remove_menu": "AI \u5de5\u5177",
                "bg_remove_title": "AI \u53bb\u80cc",
                "bg_remove_batch_title": "\u6279\u91cf AI \u53bb\u80cc",
                "bg_remove_source": "\u6765\u6e90\uff1a",
                "bg_remove_model": "\u6a21\u578b\uff1a",
                "bg_remove_alpha_matting": "Alpha matting\uff08\u8fb9\u7f18\u66f4\u5e73\u6ed1\uff0c\u8f83\u6162\uff09",
                "bg_remove_run": "\u53bb\u9664\u80cc\u666f",
                "bg_remove_done": "\u5b8c\u6210\uff01\u5df2\u4fdd\u5b58\u81f3\uff1a{path}",
                "bg_remove_done_short": "\u53bb\u80cc\u5b8c\u6210\uff01",
                "bg_remove_batch_done": "\u5df2\u5904\u7406 {success}/{total} \u5f20\u56fe\u7247",
            },
            "Japanese": {
                "bg_remove_menu": "AI \u30c4\u30fc\u30eb",
                "bg_remove_title": "AI \u80cc\u666f\u9664\u53bb",
                "bg_remove_batch_title": "\u4e00\u62ec AI \u80cc\u666f\u9664\u53bb",
                "bg_remove_source": "\u30bd\u30fc\u30b9\uff1a",
                "bg_remove_model": "\u30e2\u30c7\u30eb\uff1a",
                "bg_remove_alpha_matting": "\u30a2\u30eb\u30d5\u30a1\u30de\u30c3\u30c6\u30a3\u30f3\u30b0\uff08\u3088\u308a\u6ed1\u3089\u304b\u306a\u5883\u754c\u3001\u4f4e\u901f\uff09",
                "bg_remove_run": "\u80cc\u666f\u3092\u9664\u53bb",
                "bg_remove_done": "\u5b8c\u4e86\uff01\u4fdd\u5b58\u5148\uff1a{path}",
                "bg_remove_done_short": "\u80cc\u666f\u9664\u53bb\u5b8c\u4e86\uff01",
                "bg_remove_batch_done": "{success}/{total} \u679a\u306e\u753b\u50cf\u3092\u51e6\u7406\u3057\u307e\u3057\u305f",
            },
            "Korean": {
                "bg_remove_menu": "AI \ub3c4\uad6c",
                "bg_remove_title": "AI \ubc30\uacbd \uc81c\uac70",
                "bg_remove_batch_title": "\uc77c\uad04 AI \ubc30\uacbd \uc81c\uac70",
                "bg_remove_source": "\uc18c\uc2a4:",
                "bg_remove_model": "\ubaa8\ub378:",
                "bg_remove_alpha_matting": "\uc54c\ud30c \ub9e4\ud305 (\ub354 \ubd80\ub4dc\ub7ec\uc6b4 \uacbd\uacc4, \ub290\ub9bc)",
                "bg_remove_run": "\ubc30\uacbd \uc81c\uac70",
                "bg_remove_done": "\uc644\ub8cc! \uc800\uc7a5 \uc704\uce58: {path}",
                "bg_remove_done_short": "\ubc30\uacbd \uc81c\uac70 \uc644\ub8cc!",
                "bg_remove_batch_done": "{success}/{total}\uac1c\uc758 \uc774\ubbf8\uc9c0\ub97c \ucc98\ub9ac\ud588\uc2b5\ub2c8\ub2e4",
            },
        }
