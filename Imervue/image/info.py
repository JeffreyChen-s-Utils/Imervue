from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image
from PIL.ExifTags import TAGS
from PySide6.QtWidgets import QMessageBox

from Imervue.gpu_image_view.images.image_loader import load_image_file
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


# ==========================================================
# 取得滑鼠位置圖片資訊
# ==========================================================

def get_image_info_at_pos(main_gui: GPUImageView, position):
    mx, my = position.x(), position.y()

    # ===== Tile Grid 模式 =====
    if main_gui.tile_grid_mode:
        for x0, y0, x1, y1, path in main_gui.tile_rects:
            if x0 <= mx <= x1 and y0 <= my <= y1:
                return build_image_info(main_gui, Path(path))

    # ===== DeepZoom 模式 =====
    if main_gui.deep_zoom and 0 <= main_gui.current_index < len(main_gui.model.images):
        path = Path(main_gui.model.images[main_gui.current_index])
        return build_image_info(main_gui, path)

    return None


# ==========================================================
# 建立圖片資訊
# ==========================================================

def build_image_info(main_gui: GPUImageView, path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {}

    try:
        stat = path.stat()

        info["filename"] = path.name
        info["full_path"] = str(path)
        info["file_size_mb"] = round(stat.st_size / (1024 * 1024), 2)

        # ===== 檔案時間 =====
        ctime, mtime = get_file_times(path)
        info["created_time"] = ctime
        info["modified_time"] = mtime

        # ===== 讀取尺寸 =====
        cache_key = str(path)

        if cache_key in main_gui.tile_cache:
            img = main_gui.tile_cache[cache_key]
        else:
            img = load_image_file(path, thumbnail=True)

        h, w = img.shape[:2]
        info["width"] = w
        info["height"] = h

        # ===== EXIF =====
        exif = get_exif_data(path)
        info["exif_text"] = format_exif_info(exif)

    except Exception as e:
        info["error"] = str(e)

    return info


# ==========================================================
# 顯示 Dialog
# ==========================================================

def show_image_info_dialog(main_gui: GPUImageView, info: dict[str, Any]):
    if not info:
        return

    if "error" in info:
        QMessageBox.warning(main_gui, "Image Info Error", info["error"])
        return

    lang = language_wrapper.language_word_dict
    text = (
            lang.get("image_info_filename").format(info=info["filename"]) +
            lang.get("image_info_fullpath").format(full_path=info["full_path"]) +
            lang.get("image_info_image_size").format(
                width=info["width"], height=info["height"]) +
            lang.get("image_info_file_size").format(
                file_size_mb=info["file_size_mb"]) +
            lang.get("image_info_file_created_time").format(
                created_time=info["created_time"]) +
            lang.get("image_info_file_modified_time").format(
                modified_time=info["modified_time"]) +
            "\n====== EXIF ======\n"
            f"{info['exif_text']}"
    )

    QMessageBox.information(
        main_gui, lang.get("image_info_messagebox_title"), text
    )


# ==========================================================
# 檔案時間
# ==========================================================

def get_file_times(path: Path):
    stat = path.stat()

    mtime = datetime.fromtimestamp(stat.st_mtime)

    try:
        ctime = datetime.fromtimestamp(stat.st_ctime)
    except Exception:
        ctime = None

    return ctime, mtime


# ==========================================================
# EXIF
# ==========================================================

def get_exif_data(path: Path):
    try:
        with Image.open(path) as img:
            exif_raw = img._getexif()

        if not exif_raw:
            return {}

        return {
            TAGS.get(tag, tag): value
            for tag, value in exif_raw.items()
        }

    except Exception:
        return {}


def format_exif_info(exif: dict):
    if not exif:
        return "No EXIF data"

    def get(key):
        return exif.get(key, "N/A")

    return (
        language_wrapper.language_word_dict.get(
            "image_info_exif_datatime_original").format(DateTimeOriginal=get("DateTimeOriginal")) +
        language_wrapper.language_word_dict.get(
            "image_info_exif_camera_model").format(Make=get("Make"), Model=get("Model")) +
        language_wrapper.language_word_dict.get(
            "image_info_exif_camera_lens_model").format(LensModel=get("LensModel")) +
        language_wrapper.language_word_dict.get(
            "image_info_exif_camera_focal_length").format(FocalLength=get("FocalLength")) +
        language_wrapper.language_word_dict.get(
            "image_info_exif_camera_fnumber").format(FNumber=get("FNumber")) +
        language_wrapper.language_word_dict.get(
            "image_info_exif_exposure_time").format(ExposureTime=get("ExposureTime")) +
        language_wrapper.language_word_dict.get(
            "image_info_exif_iso").format(ISOSpeedRatings=get("ISOSpeedRatings"))
    )
