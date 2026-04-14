from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper


def build_extra_tools_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict
    menu = ui.menuBar().addMenu(lang.get("extra_tools_menu", "Extra Tools"))

    # 批次格式轉換
    convert_action = menu.addAction(
        lang.get("batch_convert_title", "Batch Format Conversion"))
    convert_action.triggered.connect(lambda: _open_batch_convert(ui))

    # AI 圖片放大
    upscale_action = menu.addAction(
        lang.get("upscale_title", "AI Image Upscale"))
    upscale_action.triggered.connect(lambda: _open_ai_upscale(ui))

    # 重複圖片偵測
    dup_action = menu.addAction(
        lang.get("duplicate_title", "Find Duplicate Images"))
    dup_action.triggered.connect(lambda: _open_duplicate_detection(ui))

    # 圖片整理工具
    organizer_action = menu.addAction(
        lang.get("organizer_title", "Image Organizer"))
    organizer_action.triggered.connect(lambda: _open_image_organizer(ui))

    # EXIF 批次清除
    strip_action = menu.addAction(
        lang.get("exif_strip_title", "Batch EXIF Strip"))
    strip_action.triggered.connect(lambda: _open_exif_strip(ui))


def _open_batch_convert(ui: ImervueMainWindow):
    from Imervue.gui.batch_convert_dialog import open_batch_convert
    open_batch_convert(ui.viewer)


def _open_ai_upscale(ui: ImervueMainWindow):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale
    open_ai_upscale(ui.viewer)


def _open_duplicate_detection(ui: ImervueMainWindow):
    from Imervue.gui.duplicate_detection_dialog import open_duplicate_detection
    open_duplicate_detection(ui.viewer)


def _open_image_organizer(ui: ImervueMainWindow):
    from Imervue.gui.image_organizer_dialog import open_image_organizer
    open_image_organizer(ui.viewer)


def _open_exif_strip(ui: ImervueMainWindow):
    from Imervue.gui.exif_strip_dialog import open_exif_strip
    open_exif_strip(ui.viewer)
