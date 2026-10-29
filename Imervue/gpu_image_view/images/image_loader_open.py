"""Open a folder or a file into the viewer: the progressive folder scan and the state it sets.

Split out of :mod:`image_loader`, whose :func:`open_path` dispatches here and
which re-exports every name callers use.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThreadPool

from Imervue.system.best_effort import best_effort
from Imervue.image.heif_support import ensure_heif_opener
from Imervue.gpu_image_view.images.image_loader_scan import (
    FolderScanWorker,
    _scan_images_for_user,
    _sort_for_user,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _maybe_collapse_stacks(images: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Collapse RAW+JPEG pairs when the user has the setting enabled."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    if not user_setting_dict.get("stack_raw_jpeg_pairs"):
        return list(images), {}
    from Imervue.library.stacks import collapse_stacks
    return collapse_stacks(list(images))


def _maybe_hint_heif(main_gui: GPUImageView, images: list[str]) -> None:
    """Toast once per window when a folder has HEIC but no decoder."""
    from Imervue.image.heif_support import needs_heif_hint
    if not needs_heif_hint(images, ensure_heif_opener()):
        return
    main_window = getattr(main_gui, "main_window", None)
    toast = getattr(main_window, "toast", None)
    if toast is None or getattr(main_window, "_heif_hint_shown", False):
        return
    main_window._heif_hint_shown = True
    from Imervue.multi_language.language_wrapper import language_wrapper
    toast.info(language_wrapper.language_word_dict.get(
        "heif_install_hint",
        "Install pillow-heif to view HEIC images.",
    ))


def _open_folder(main_gui: GPUImageView, path_obj: Path) -> None:
    _open_folder_progressive(main_gui, path_obj)


def _open_folder_progressive(main_gui: GPUImageView, path_obj: Path) -> None:
    from Imervue.gpu_image_view.images.folder_scan_updates import FolderScanUpdates
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    from Imervue.user_settings.recent_image import add_recent_folder
    cancel_folder_scan(main_gui)
    main_gui._folder_scan_updates = FolderScanUpdates(
        lambda images: _apply_folder_scan_paths(main_gui, images), main_gui)
    generation = main_gui._folder_scan_generation
    main_gui.current_index = 0
    main_gui._unfiltered_images = []
    main_gui._stack_members = {}
    # Set before the wall is emptied so the very first paint of the now-blank
    # grid already shows the spinner instead of a bare dark canvas.
    main_gui._folder_scan_active = True
    main_gui.load_tile_grid_async([])

    worker = FolderScanWorker(str(path_obj))
    worker.signals.batch.connect(
        lambda folder, batch, gen=generation: _on_folder_scan_batch(
            main_gui, folder, batch, gen,
        )
    )
    worker.signals.finished.connect(
        lambda folder, images, gen=generation: _on_folder_scan_finished(
            main_gui, folder, images, gen,
        )
    )
    main_gui._folder_scan_worker = worker
    QThreadPool.globalInstance().start(worker)
    main_gui.current_index = 0
    add_recent_folder(str(path_obj))
    user_setting_dict["user_last_folder"] = str(path_obj)


def cancel_folder_scan(main_gui: GPUImageView) -> None:
    """Discard pending scan work before another path opens or the viewer is destroyed."""
    main_gui._folder_scan_generation = getattr(main_gui, "_folder_scan_generation", 0) + 1
    worker = getattr(main_gui, "_folder_scan_worker", None)
    if worker is not None:
        with best_effort("abort the previous folder scan"):
            worker.abort()
    updates = getattr(main_gui, "_folder_scan_updates", None)
    if updates is not None:
        updates.cancel()
        updates.deleteLater()
    main_gui._folder_scan_worker = None
    main_gui._folder_scan_updates = None
    main_gui._folder_scan_active = False


def _on_folder_scan_batch(main_gui: GPUImageView, _folder: str, batch: list[str],
                          generation: int) -> None:
    if generation != getattr(main_gui, "_folder_scan_generation", None):
        return
    main_gui._folder_scan_updates.add(batch)


def _on_folder_scan_finished(main_gui: GPUImageView, folder: str, images: list[str],
                             generation: int) -> None:
    if generation != getattr(main_gui, "_folder_scan_generation", None):
        return
    main_gui._folder_scan_worker = None
    # Scan over — an empty wall from here on means an empty folder, not a slow
    # one, so the spinner must stop rather than hang forever.
    main_gui._folder_scan_active = False
    _maybe_hint_heif(main_gui, images)
    main_gui._folder_scan_updates.finish(images)
    if not main_gui.model.images:
        hide_progress = getattr(main_gui.main_window, "_hide_progress", None)
        if callable(hide_progress):
            hide_progress()
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_folder_opened(
            folder, images, main_gui,
        )


def _apply_folder_scan_paths(main_gui: GPUImageView, images: list[str]) -> None:
    main_gui._unfiltered_images = list(images)
    collapsed, stacks = _maybe_collapse_stacks(images)
    main_gui._stack_members = stacks
    if hasattr(main_gui.main_window, "_apply_refreshed_image_list"):
        main_gui.main_window._apply_refreshed_image_list(collapsed)
    else:
        main_gui.load_tile_grid_async(collapsed)


def _open_file(main_gui: GPUImageView, path_obj: Path) -> None:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    from Imervue.user_settings.recent_image import add_recent_image
    cancel_folder_scan(main_gui)
    dir_path = path_obj.parent
    images = _scan_images_for_user(str(dir_path))
    target = os.path.normpath(str(path_obj))
    if all(os.path.normpath(p) != target for p in images):
        # A hidden picture opened on purpose joins its folder's list.
        images = _sort_for_user([*images, str(path_obj)])
    main_gui._unfiltered_images = list(images)
    images, stacks = _maybe_collapse_stacks(images)
    main_gui._stack_members = stacks
    main_gui.model.set_images(images)
    main_gui.current_index = _locate_current_index(images, str(path_obj))
    main_gui.tile_grid_mode = False
    main_gui.load_deep_zoom_image(str(path_obj))
    # Opening a specific file rebuilt the list from the whole folder above,
    # dropping any active browse filter — re-apply it (keeping this file visible).
    reapply = getattr(main_gui.main_window, "_reapply_filter_preserving_current", None)
    if callable(reapply):
        reapply()
    add_recent_image(str(path_obj))
    user_setting_dict["user_last_folder"] = str(dir_path)


def _locate_current_index(images: list[str], target: str) -> int:
    try:
        return images.index(target)
    except ValueError:
        import os
        norm = os.path.normpath(target)
        for i, p in enumerate(images):
            if os.path.normpath(p) == norm:
                return i
        return 0
