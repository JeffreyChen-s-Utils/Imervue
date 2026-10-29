"""Relocate missing images and retry failed deep-zoom or thumbnail loads."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QMenu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.gui.file_filters import viewer_filter
from Imervue.menu.right_click_current import _current_image_path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _relocate_missing_action(main_gui: GPUImageView, menu: QMenu) -> None:
    path = _current_image_path(main_gui)
    if not path or Path(path).exists():
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(
        lang.get("missing_relocate", "Relocate Missing File..."),
    )
    action.triggered.connect(lambda: _relocate_missing(main_gui, path))


def _relocate_missing(main_gui: GPUImageView, old_path: str) -> None:
    from PySide6.QtWidgets import QFileDialog

    lang = language_wrapper.language_word_dict
    new_path, _ = QFileDialog.getOpenFileName(
        main_gui,
        lang.get("missing_relocate", "Relocate Missing File..."),
        str(Path(old_path).parent),
        viewer_filter(),
    )
    if not new_path:
        return
    try:
        idx = main_gui.model.images.index(old_path)
    except ValueError:
        idx = main_gui.current_index
    if 0 <= idx < len(main_gui.model.images):
        main_gui.model.images[idx] = new_path
        main_gui.current_index = idx
    main_gui.offline_paths.discard(old_path)
    main_gui.tile_errors.pop(old_path, None)
    main_gui._deep_zoom_error = None
    main_gui.load_deep_zoom_image(new_path)


def _retry_load_action(main_gui: GPUImageView, menu: QMenu) -> None:
    path = _current_image_path(main_gui)
    tile_path = getattr(main_gui, "_hover_tile_path", None)
    if tile_path in getattr(main_gui, "tile_errors", {}):
        path = tile_path
    elif getattr(main_gui, "_deep_zoom_error", None):
        path = main_gui._deep_zoom_error[0]
    if not path:
        return
    if path not in getattr(main_gui, "tile_errors", {}) and (
        not getattr(main_gui, "_deep_zoom_error", None) or main_gui._deep_zoom_error[0] != path
    ):
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("image_retry_load", "Retry Load"))
    action.triggered.connect(lambda: _retry_load(main_gui, path))


def _retry_load(main_gui: GPUImageView, path: str) -> None:
    if getattr(main_gui, "_deep_zoom_error", None) and main_gui._deep_zoom_error[0] == path:
        main_gui._deep_zoom_error = None
        main_gui.load_deep_zoom_image(path)
        return
    if path in getattr(main_gui, "tile_errors", {}):
        from Imervue.gpu_image_view.tile_loader import _retry_thumbnail

        main_gui.tile_errors.pop(path, None)
        _retry_thumbnail(main_gui, path, main_gui._load_generation)
