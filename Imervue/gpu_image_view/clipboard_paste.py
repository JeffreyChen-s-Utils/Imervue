"""Clipboard image-paste flow for :class:`GPUImageView`.

Pulls a bitmap (or a file URL) off the system clipboard, saves it next to
the current folder, inserts it into the image model, and opens it. Kept
out of the view so the QWidget stays focused on GL + event routing.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def paste_image_from_clipboard(view: GPUImageView) -> None:
    """從剪貼簿貼上圖片，儲存到目前資料夾並載入。"""
    clipboard = QApplication.clipboard()
    qimg = clipboard.image()
    if qimg.isNull():
        _open_clipboard_url_if_any(view, clipboard)
        return

    folder = _resolve_paste_target_folder(view)
    if folder is None:
        return

    save_path = _save_clipboard_image(qimg, folder)
    _load_pasted_image(view, save_path)


def _open_clipboard_url_if_any(view: GPUImageView, clipboard) -> None:
    """If the clipboard holds a file URL, open it in the viewer."""
    mime = clipboard.mimeData()
    if not (mime and mime.hasUrls()):
        return
    for url in mime.urls():
        local_path = url.toLocalFile()
        if local_path and Path(local_path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            open_path(main_gui=view, path=local_path)
            return


def _resolve_paste_target_folder(view: GPUImageView) -> str | None:
    """Pick the folder where a pasted clipboard image should land."""
    images = view.model.images
    if images:
        folder = str(Path(images[0]).parent)
    else:
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        folder = user_setting_dict.get("user_last_folder", "")
    if not folder or not Path(folder).is_dir():
        return None
    return folder


def _save_clipboard_image(qimg, folder: str) -> str:
    """Persist ``qimg`` under ``folder`` with a timestamped name."""
    name = f"pasted_{int(time.time())}.png"
    save_path = str(Path(folder) / name)
    qimg.save(save_path, "PNG")
    return save_path


def _load_pasted_image(view: GPUImageView, save_path: str) -> None:
    """Insert the saved file into the model and open it in the viewer."""
    images = view.model.images
    if save_path not in images:
        images.append(save_path)
        images.sort(key=lambda p: os.path.basename(p).lower())

    from Imervue.gpu_image_view.images.image_loader import open_path
    open_path(main_gui=view, path=save_path)

    if hasattr(view.main_window, "toast"):
        view.main_window.toast.info(f"Pasted: {Path(save_path).name}")
