"""Build current-image clipboard, reveal, export, wallpaper and OCR actions."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import QThreadPool
from Imervue.gpu_image_view.actions.keyboard_actions import copy_image_to_clipboard
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.gui.export_dialog import open_export_dialog
from functools import partial
from Imervue.system.file_manager import reveal_or_warn
from Imervue.system.wallpaper import set_desktop_wallpaper
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _current_image_path(main_gui: GPUImageView) -> str | None:
    images = main_gui.model.images
    if not images:
        return None
    if getattr(main_gui, "_deep_zoom_error", None):
        return main_gui._deep_zoom_error[0]
    if main_gui.deep_zoom and 0 <= main_gui.current_index < len(images):
        return images[main_gui.current_index]
    return None


def _show_in_explorer_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return

    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_show_in_explorer", "Show in Explorer"))
    action.triggered.connect(lambda: reveal_or_warn(path))


def _copy_path_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return

    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_copy_path", "Copy Path"))

    def _do_copy_path():
        QApplication.clipboard().setText(path)
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.info(
                language_wrapper.language_word_dict.get("toast_path_copied", "Path copied")
            )

    action.triggered.connect(_do_copy_path)


def _copy_image_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.deep_zoom:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_copy_image", "Copy Image"))
    action.triggered.connect(lambda: copy_image_to_clipboard(main_gui))


def _export_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_export", "Export / Save As..."))
    action.triggered.connect(lambda: open_export_dialog(main_gui))


def _set_wallpaper_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return

    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_set_wallpaper", "Set as Wallpaper"))
    # Off the GUI thread: a RAW or HEIC is decoded into a JPEG copy first.
    action.triggered.connect(
        lambda: QThreadPool.globalInstance().start(partial(set_desktop_wallpaper, path))
    )


def _ocr_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.deep_zoom:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("ocr_extract", "Extract Text (OCR)"))
    action.triggered.connect(lambda: _open_ocr(main_gui))


def _open_ocr(main_gui: GPUImageView):
    from Imervue.gui.ocr_dialog import open_ocr

    open_ocr(main_gui)
