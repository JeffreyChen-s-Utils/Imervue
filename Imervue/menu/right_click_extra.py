"""Build optional-tool actions and load their dialogs on activation."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from Imervue.multi_language.language_wrapper import language_wrapper
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _extra_tools_submenu(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict
    extra_menu = menu.addMenu(lang.get("extra_tools_menu", "Extra Tools"))

    # 批次格式轉換
    if main_gui.model.images:
        action = extra_menu.addAction(lang.get("batch_convert_title", "Batch Format Conversion"))
        action.triggered.connect(lambda: _do_batch_convert(main_gui))

    # AI 圖片放大 — single image
    if main_gui.deep_zoom:
        images = main_gui.model.images
        if images and 0 <= main_gui.current_index < len(images):
            path = images[main_gui.current_index]
            action = extra_menu.addAction(lang.get("upscale_quick", "AI Upscale — Current Image"))
            action.triggered.connect(lambda: _do_upscale_single(main_gui, path))
    # AI 圖片放大 — batch
    if main_gui.tile_grid_mode and main_gui.tile_selection_mode and main_gui.selected_tiles:
        action = extra_menu.addAction(lang.get("upscale_batch", "AI Upscale — Selected Images"))
        action.triggered.connect(lambda: _do_upscale_batch(main_gui))

    # 重複圖片偵測
    if main_gui.model.images:
        action = extra_menu.addAction(lang.get("duplicate_title", "Find Duplicate Images"))
        action.triggered.connect(lambda: _do_duplicate_detection(main_gui))

    # 圖片整理工具
    if main_gui.model.images:
        action = extra_menu.addAction(lang.get("organizer_title", "Image Organizer"))
        action.triggered.connect(lambda: _do_image_organizer(main_gui))

    # EXIF 批次清除
    if main_gui.model.images:
        action = extra_menu.addAction(lang.get("exif_strip_title", "Batch EXIF Strip"))
        action.triggered.connect(lambda: _do_exif_strip(main_gui))

    # 圖片淨化重繪
    if main_gui.model.images:
        action = extra_menu.addAction(lang.get("sanitize_title", "Image Sanitizer"))
        action.triggered.connect(lambda: _do_image_sanitize(main_gui))


def _do_batch_convert(main_gui: GPUImageView):
    from Imervue.gui.batch_convert_dialog import open_batch_convert

    open_batch_convert(main_gui)


def _do_upscale_single(main_gui: GPUImageView, path: str):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale_single

    open_ai_upscale_single(main_gui, path)


def _do_upscale_batch(main_gui: GPUImageView):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale_batch

    open_ai_upscale_batch(main_gui)


def _do_duplicate_detection(main_gui: GPUImageView):
    from Imervue.gui.duplicate_detection_dialog import open_duplicate_detection

    open_duplicate_detection(main_gui)


def _do_image_organizer(main_gui: GPUImageView):
    from Imervue.gui.image_organizer_dialog import open_image_organizer

    open_image_organizer(main_gui)


def _do_exif_strip(main_gui: GPUImageView):
    from Imervue.gui.exif_strip_dialog import open_exif_strip

    open_exif_strip(main_gui)


def _do_image_sanitize(main_gui: GPUImageView):
    from Imervue.gui.image_sanitize_dialog import open_image_sanitize

    open_image_sanitize(main_gui)
