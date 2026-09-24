"""
PNG to Icon Converter Plugin
Convert PNG images into multi-size .ico and .png icon files.

Pillow is part of the main program's default dependency set, so the plugin
needs no extra install step.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageOps
from PySide6.QtWidgets import QFileDialog, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu

    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.png_to_icon")

SIZES = (16, 32, 48, 64, 128, 256)
OUTPUT_DIR_NAME = "icons"


def icon_output_dir(source: str | Path) -> Path:
    """Return the directory the icon set for ``source`` is written to."""
    return Path(source).parent / OUTPUT_DIR_NAME


def write_icon_set(source: str | Path, sizes: tuple[int, ...] = SIZES) -> list[Path]:
    """Write one square PNG and one ICO per size next to ``source``.

    Returns the written paths in size order (PNG before ICO for each size).
    Raises ``ValueError`` for an empty or non-positive size list and lets
    Pillow's ``OSError`` through for an unreadable source.
    """
    if not sizes or any(size <= 0 for size in sizes):
        raise ValueError(f"icon sizes must be positive, got {sizes!r}")
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")   # upright, as shown
    output_dir = icon_output_dir(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for size in sizes:
        resized = image.resize((size, size), Image.Resampling.LANCZOS)
        png_path = output_dir / f"icon_{size}x{size}.png"
        ico_path = output_dir / f"icon_{size}x{size}.ico"
        resized.save(png_path)
        resized.save(ico_path, format="ICO", sizes=[(size, size)])
        written.extend((png_path, ico_path))
    return written


class IconConverterPlugin(ImervuePlugin):
    """Menu and context-menu entries that turn a PNG into an icon set."""

    plugin_name = "PNG to Icon Converter"
    plugin_version = "1.6.0"
    plugin_description = "Convert PNG images into multi-size icons"
    plugin_author = "JE Chen"

    def _lang(self) -> dict:
        return language_wrapper.language_word_dict

    # ===========================
    # Menu Hooks
    # ===========================

    def on_build_menu_bar(self, plugin_menu: QMenu) -> None:
        lang = self._lang()
        menu = plugin_menu.addMenu(lang.get("icon_tools_menu", "Icon Tools"))

        action = menu.addAction(lang.get("convert_current", "Convert Current Image to Icon"))
        action.triggered.connect(self._convert_current)

        action2 = menu.addAction(lang.get("select_png", "Select PNG to Convert"))
        action2.triggered.connect(self._select_and_convert)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        if not viewer.deep_zoom:
            return
        lang = self._lang()
        action = menu.addAction(lang.get("context_convert", "Convert to Icon"))
        action.triggered.connect(self._convert_current)

    # ===========================
    # Entry points
    # ===========================

    def _convert_current(self) -> None:
        lang = self._lang()
        if not self.viewer.deep_zoom:
            QMessageBox.warning(
                self.main_window,
                lang.get("error", "Error"),
                lang.get("no_image", "No image loaded"),
            )
            return
        self._convert_to_icon(self.viewer.model.images[self.viewer.current_index])

    def _select_and_convert(self) -> None:
        lang = self._lang()
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            lang.get("select_title", "Select PNG"),
            "",
            "PNG Files (*.png)",
        )
        if file_path:
            self._convert_to_icon(file_path)

    def _convert_to_icon(self, file_path: str) -> None:
        lang = self._lang()
        try:
            write_icon_set(file_path)
        except (OSError, ValueError) as exc:
            logger.exception("Icon conversion failed for %s", file_path)
            QMessageBox.critical(
                self.main_window,
                lang.get("error", "Error"),
                str(exc),
            )
            return
        QMessageBox.information(
            self.main_window,
            "OK",
            f"{lang.get('success', 'Icons saved to:')} \n{icon_output_dir(file_path)}",
        )

    # ===========================
    # Translations
    # ===========================

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "icon_tools_menu": "Icon Tools",
                "convert_current": "Convert Current Image to Icon",
                "select_png": "Select PNG to Convert",
                "context_convert": "Convert to Icon",
                "no_image": "No image loaded",
                "success": "Icons saved to:",
                "error": "Error",
                "select_title": "Select PNG",
            },
            "Traditional_Chinese": {
                "icon_tools_menu": "Icon 工具",
                "convert_current": "轉換目前圖片為 Icon",
                "select_png": "選擇 PNG 轉換",
                "context_convert": "轉換為 Icon",
                "no_image": "尚未載入圖片",
                "success": "已輸出到：",
                "error": "錯誤",
                "select_title": "選擇 PNG",
            },
            "Chinese": {
                "icon_tools_menu": "Icon 工具",
                "convert_current": "转换当前图片为 Icon",
                "select_png": "选择 PNG 转换",
                "context_convert": "转换为 Icon",
                "no_image": "尚未加载图片",
                "success": "已输出到：",
                "error": "错误",
                "select_title": "选择 PNG",
            },
            "Japanese": {
                "icon_tools_menu": "アイコンツール",
                "convert_current": "現在の画像をアイコンに変換",
                "select_png": "PNGを選択して変換",
                "context_convert": "アイコンに変換",
                "no_image": "画像が読み込まれていません",
                "success": "保存先：",
                "error": "エラー",
                "select_title": "PNGを選択",
            },
            "Korean": {
                "icon_tools_menu": "아이콘 도구",
                "convert_current": "현재 이미지를 아이콘으로 변환",
                "select_png": "PNG 선택 후 변환",
                "context_convert": "아이콘으로 변환",
                "no_image": "이미지가 로드되지 않음",
                "success": "저장 위치:",
                "error": "오류",
                "select_title": "PNG 선택",
            },
        }
