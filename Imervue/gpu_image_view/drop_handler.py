"""Drag-and-drop file/folder opening for :class:`GPUImageView`.

Handles a drop of local file/folder URLs: opens the first dropped path,
points the tree + breadcrumb at it, records it in recents, and starts a
folder watch. Extracted so the view keeps a thin ``dropEvent`` forwarder.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_FOLDER_LABEL_KEY = "main_window_current_folder_format"
_FOLDER_LABEL_FALLBACK = "Current Folder: {path}"


def handle_drop(view: GPUImageView, event) -> None:
    """Open the first locally-dropped file or folder."""
    urls = event.mimeData().urls()
    if not urls:
        return
    paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
    if not paths:
        return

    view.clear_tile_grid()
    first = paths[0]
    if Path(first).is_dir():
        _open_dropped_folder(view, first)
    elif Path(first).is_file():
        _open_dropped_file(view, first)

    from Imervue.menu.recent_menu import rebuild_recent_menu
    rebuild_recent_menu(view.main_window)
    event.acceptProposedAction()


def _open_dropped_folder(view: GPUImageView, folder: str) -> None:
    from Imervue.gpu_image_view.images.image_loader import open_path
    from Imervue.user_settings.recent_image import add_recent_folder
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    mw = view.main_window
    lang = mw.language_wrapper.language_word_dict
    mw.model.setRootPath(folder)
    mw.tree.setRootIndex(mw.model.index(folder))
    open_path(main_gui=view, path=folder)
    mw.filename_label.setText(
        lang.get(_FOLDER_LABEL_KEY, _FOLDER_LABEL_FALLBACK).format(path=folder)
    )
    if hasattr(mw, "breadcrumb"):
        mw.breadcrumb.set_path(folder)
    add_recent_folder(folder)
    user_setting_dict["user_last_folder"] = folder
    mw.watch_folder(folder)


def _open_dropped_file(view: GPUImageView, file_path: str) -> None:
    from Imervue.gpu_image_view.images.image_loader import open_path
    from Imervue.user_settings.recent_image import add_recent_image
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    mw = view.main_window
    folder = str(Path(file_path).parent)
    mw.model.setRootPath(folder)
    mw.tree.setRootIndex(mw.model.index(folder))
    open_path(main_gui=view, path=file_path)
    if hasattr(mw, "breadcrumb"):
        mw.breadcrumb.set_path(folder)
    add_recent_image(file_path)
    user_setting_dict["user_last_folder"] = folder
    mw.watch_folder(folder)
