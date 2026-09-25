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
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.natural_sort import natural_key

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def paste_image_from_clipboard(view: GPUImageView) -> None:
    """從剪貼簿貼上圖片，儲存到目前資料夾並載入。"""
    clipboard = QApplication.clipboard()
    qimg = clipboard.image()
    if qimg.isNull():
        if not _open_clipboard_url_if_any(view, clipboard):
            _toast(view, "info", _text("file_menu_paste_clipboard_empty",
                                       "Clipboard does not contain an image"))
        return

    folder = _resolve_paste_target_folder(view)
    if folder is None:
        _toast(view, "info", _text("paste_no_folder",
                                   "Open a folder first: a pasted image is saved into it"))
        return

    save_path = _save_clipboard_image(qimg, folder)
    if save_path is None:
        _toast(view, "error", _text("paste_save_failed",
                                    "Could not save the pasted image to {folder}", folder=folder))
        return
    _load_pasted_image(view, save_path)


def _open_clipboard_url_if_any(view: GPUImageView, clipboard) -> bool:
    """If the clipboard holds a file URL, open it in the viewer; True when one was opened."""
    mime = clipboard.mimeData()
    if not (mime and mime.hasUrls()):
        return False
    for url in mime.urls():
        local_path = url.toLocalFile()
        if local_path and Path(local_path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            open_path(main_gui=view, path=local_path)
            return True
    return False


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


def _save_clipboard_image(qimg, folder: str) -> str | None:
    """Persist ``qimg`` under ``folder`` with a timestamped name; ``None`` if the write fails.

    A second paste within the same second gets a ``-1`` / ``-2`` suffix instead
    of overwriting the first. ``QImage.save`` never raises; it returns ``False``.
    """
    stem = f"pasted_{int(time.time())}"
    save_path = Path(folder) / f"{stem}.png"
    counter = 1
    while save_path.exists():
        save_path = Path(folder) / f"{stem}-{counter}.png"
        counter += 1
    return str(save_path) if qimg.save(str(save_path), "PNG") else None


def _load_pasted_image(view: GPUImageView, save_path: str) -> None:
    """Insert the saved file into the model and open it in the viewer."""
    images = view.model.images
    if save_path not in images:
        images.append(save_path)
        images.sort(key=lambda p: natural_key(os.path.basename(p)))

    from Imervue.gpu_image_view.images.image_loader import open_path
    open_path(main_gui=view, path=save_path)

    _toast(view, "info", _text("paste_saved", "Pasted: {name}", name=Path(save_path).name))


def _text(key: str, fallback: str, **fields: str) -> str:
    """The toast text *key* in the current language, *fields* filled in."""
    return language_wrapper.language_word_dict.get(key, fallback).format(**fields)


def _toast(view: GPUImageView, level: str, text: str) -> None:
    if hasattr(view.main_window, "toast"):
        getattr(view.main_window.toast, level)(text)
