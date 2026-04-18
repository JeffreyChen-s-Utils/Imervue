from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF

from Imervue.user_settings.user_setting_dict import user_setting_dict
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _auto_loop_enabled() -> bool:
    """Whether arrow keys at list ends should wrap around.

    Default True — users expect last→first / first→last to be seamless when
    browsing a folder. Stored under ``navigation_auto_loop`` in settings.
    """
    return bool(user_setting_dict.get("navigation_auto_loop", True))


def _notify_switch(main_gui: GPUImageView, path: str) -> None:
    """Dispatch plugin hook for image switch (shared by prev/next)."""
    pm = getattr(main_gui.main_window, "plugin_manager", None)
    if pm is not None:
        with contextlib.suppress(Exception):
            pm.dispatch_image_switched(path, main_gui)


def switch_to_next_image(main_gui: GPUImageView) -> None:
    images = main_gui.model.images

    if not images:
        return

    if main_gui.current_index < len(images) - 1:
        main_gui.current_index += 1
    elif _auto_loop_enabled():
        main_gui.current_index = 0
        _toast_loop(main_gui, forward=True)
    else:
        main_gui.update()
        return

    main_gui.load_deep_zoom_image(images[main_gui.current_index])
    _notify_switch(main_gui, images[main_gui.current_index])
    main_gui.update()


def switch_to_previous_image(main_gui: GPUImageView) -> None:
    images = main_gui.model.images

    if not images:
        return

    if main_gui.current_index > 0:
        main_gui.current_index -= 1
    elif _auto_loop_enabled():
        main_gui.current_index = len(images) - 1
        _toast_loop(main_gui, forward=False)
    else:
        main_gui.update()
        return

    main_gui.load_deep_zoom_image(images[main_gui.current_index])
    _notify_switch(main_gui, images[main_gui.current_index])
    main_gui.update()


def _toast_loop(main_gui: GPUImageView, forward: bool) -> None:
    """Show a small toast when wrapping around the gallery."""
    mw = main_gui.main_window
    if not hasattr(mw, "toast"):
        return
    lang = mw.language_wrapper.language_word_dict
    key = "nav_loop_next" if forward else "nav_loop_prev"
    fallback = "Looped to first image" if forward else "Looped to last image"
    with contextlib.suppress(Exception):
        mw.toast.info(lang.get(key, fallback))


def switch_to_next_folder(main_gui: GPUImageView) -> None:
    """Jump to the first image of the next sibling folder that contains images."""
    _switch_sibling_folder(main_gui, direction=1)


def switch_to_previous_folder(main_gui: GPUImageView) -> None:
    """Jump to the first image of the previous sibling folder that contains images."""
    _switch_sibling_folder(main_gui, direction=-1)


def _switch_sibling_folder(main_gui: GPUImageView, direction: int) -> None:
    """Scan sibling directories in alphabetical order and open the first that has images."""
    images = main_gui.model.images
    if not images:
        return

    current_folder = Path(images[0]).parent
    parent = current_folder.parent
    if not parent.exists():
        return

    try:
        siblings = sorted(
            (p for p in parent.iterdir() if p.is_dir()),
            key=lambda p: p.name.lower(),
        )
    except OSError:
        return

    if not siblings:
        return

    try:
        idx = siblings.index(current_folder)
    except ValueError:
        idx = 0

    # 掃描下一個/上一個有圖片的兄弟資料夾（最多走完一圈）
    from Imervue.gpu_image_view.images.image_loader import _scan_images, open_path
    for step in range(1, len(siblings) + 1):
        next_idx = (idx + direction * step) % len(siblings)
        candidate = siblings[next_idx]
        found = _scan_images(str(candidate))
        if found:
            mw = main_gui.main_window
            lang = mw.language_wrapper.language_word_dict
            mw.model.setRootPath(str(candidate))
            mw.tree.setRootIndex(mw.model.index(str(candidate)))
            main_gui.clear_tile_grid()
            open_path(main_gui=main_gui, path=str(candidate))
            mw.filename_label.setText(
                lang.get(
                    "main_window_current_folder_format",
                    "Current Folder: {path}",
                ).format(path=str(candidate))
            )
            if hasattr(mw, "breadcrumb"):
                mw.breadcrumb.set_path(str(candidate))
            mw.watch_folder(str(candidate))
            user_setting_dict["user_last_folder"] = str(candidate)
            if hasattr(mw, "toast"):
                key = "nav_folder_next" if direction > 0 else "nav_folder_prev"
                fallback = "Next folder: {name}" if direction > 0 else "Previous folder: {name}"
                mw.toast.info(lang.get(key, fallback).format(name=candidate.name))
            return


def select_tiles_in_rect(start_pos, end_pos, main_gui: GPUImageView):
    if start_pos is None or end_pos is None:
        return

    x0, y0 = start_pos.x(), start_pos.y()
    x1, y1 = end_pos.x(), end_pos.y()
    rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

    for tx0, ty0, tx1, ty1, path in main_gui.tile_rects:
        tile_rect = QRectF(tx0, ty0, tx1 - tx0, ty1 - ty0)
        if rect.intersects(tile_rect):
            main_gui.selected_tiles.add(path)

def start_tile_selection(main_gui: GPUImageView):
    if not main_gui.press_pos:
        return

    main_gui.tile_selection_mode = True
    main_gui._drag_selecting = True
    main_gui._drag_start_pos = main_gui.press_pos
    main_gui._drag_end_pos = main_gui.press_pos

    main_gui.update()
