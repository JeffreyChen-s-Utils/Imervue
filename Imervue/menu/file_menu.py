from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QFileDialog

from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import load_image
from Imervue.menu.recent_menu import rebuild_recent_menu, build_recent_menu
from Imervue.user_settings.recent_image import add_to_recent, add_recent_folder, add_recent_image
from Imervue.user_settings.user_setting_dict import user_setting_dict

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper


def build_file_menu(ui_we_want_to_set: ImervueMainWindow):
    # ===== 檔案 =====
    file_menu = ui_we_want_to_set.menuBar().addMenu(language_wrapper.language_word_dict.get("main_window_current_file"))

    open_image_action = file_menu.addAction(
        language_wrapper.language_word_dict.get("main_window_open_image")
    )
    open_image_action.triggered.connect(
        lambda: open_image(ui_we_want_to_set)
    )

    open_folder_action = file_menu.addAction(language_wrapper.language_word_dict.get("main_window_open_folder"))
    open_folder_action.triggered.connect(lambda: open_folder(ui_we_want_to_set))

    build_recent_menu(ui_we_want_to_set=ui_we_want_to_set, menu=file_menu)

    # 新增刪除動作
    delete_action = file_menu.addAction(language_wrapper.language_word_dict.get("main_window_remove_undo_stack"))
    delete_action.triggered.connect(lambda: commit_pending_deletions(ui_we_want_to_set.viewer))

    exit_action = file_menu.addAction(language_wrapper.language_word_dict.get("main_window_exit"))
    exit_action.triggered.connect(ui_we_want_to_set.close)

    # ===== Tile Size 選單 =====
    view_menu = ui_we_want_to_set.menuBar().addMenu(language_wrapper.language_word_dict.get("main_window_tile_size"))

    tile_group = QActionGroup(ui_we_want_to_set)
    tile_group.setExclusive(True)

    thumbnail_size = [128, 256, 512, 1024, "None"]

    for size in thumbnail_size:
        if size != "None":
            action = view_menu.addAction(f"{size} x {size}")
        else:
            action = view_menu.addAction(size)
        action.setCheckable(True)

        if size == ui_we_want_to_set.viewer.thumbnail_size:
            action.setChecked(True)

        tile_group.addAction(action)

        action.triggered.connect(
            lambda checked, s=size: ui_we_want_to_set.change_tile_size(s)
        )
    return file_menu


# ==========================
# 開啟資料夾
# ==========================
def open_folder(ui_we_want_to_set: ImervueMainWindow):
    folder = QFileDialog.getExistingDirectory(
        ui_we_want_to_set, language_wrapper.language_word_dict.get("main_window_select_folder"))

    if folder:
        ui_we_want_to_set.tree.setRootIndex(ui_we_want_to_set.model.index(folder))
        add_recent_folder(folder)
        rebuild_recent_menu(ui_we_want_to_set)
        user_setting_dict["user_last_folder"] = folder

# ==========================
# 開啟單張圖片
# ==========================
def open_image(ui_we_want_to_set: ImervueMainWindow):
    file_path, _ = QFileDialog.getOpenFileName(
        ui_we_want_to_set,
        language_wrapper.language_word_dict.get("main_window_select_image"),
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.tiff)"
    )

    if not file_path:
        return

    # 清除 tile grid 狀態
    ui_we_want_to_set.viewer.clear_tile_grid()

    # 呼叫你提供的函式
    load_image(file_path, ui_we_want_to_set.viewer)

    # 設定 viewer 狀態
    ui_we_want_to_set.viewer.tile_grid_mode = False
    ui_we_want_to_set.viewer.current_index = 0
    ui_we_want_to_set.viewer.model.set_images([file_path])

    # 更新檔名 label
    ui_we_want_to_set.filename_label.setText(
        language_wrapper.language_word_dict.get(
            "main_window_current_filename_format"
        ).format(name=Path(file_path).name))

    add_recent_image(file_path)
    rebuild_recent_menu(ui_we_want_to_set)

