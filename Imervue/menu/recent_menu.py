from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMenu

from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.recent_image import clear_recent, add_recent_folder, add_recent_image
from Imervue.user_settings.user_setting_dict import user_setting_dict


def build_recent_menu(ui_we_want_to_set, menu: QMenu):
    # ===== Recent =====
    recent_menu = menu.addMenu(language_wrapper.language_word_dict.get("recent_menu_title"))

    recent_folder_menu = recent_menu.addMenu("Recent Folders")
    recent_image_menu = recent_menu.addMenu("Recent Images")

    ui_we_want_to_set._recent_folder_menu = recent_folder_menu
    ui_we_want_to_set._recent_image_menu = recent_image_menu
    ui_we_want_to_set._recent_menu = recent_menu

    recent_menu.addSeparator()

    clear_action = recent_menu.addAction("Clear Recent")
    clear_action.triggered.connect(
        lambda: handle_clear_recent(ui_we_want_to_set)
    )

    rebuild_recent_menu(ui_we_want_to_set)


def rebuild_recent_menu(ui_we_want_to_set):
    folder_menu = ui_we_want_to_set._recent_folder_menu
    image_menu = ui_we_want_to_set._recent_image_menu

    folder_menu.clear()
    image_menu.clear()

    # ===== Folders =====
    valid_folders = []
    for path in user_setting_dict.get("user_recent_folders", []):
        if Path(path).is_dir():
            valid_folders.append(path)

            icon = ui_we_want_to_set.model.fileIcon(
                ui_we_want_to_set.model.index(path)
            )
            action = folder_menu.addAction(icon, path)
            action.triggered.connect(
                lambda checked, p=path: open_recent(ui_we_want_to_set, p)
            )

    user_setting_dict["user_recent_folders"] = valid_folders

    if not valid_folders:
        empty = folder_menu.addAction("(Empty)")
        empty.setEnabled(False)

    # ===== Images =====
    valid_images = []
    for path in user_setting_dict.get("user_recent_images", []):
        if Path(path).is_file():
            valid_images.append(path)

            action = image_menu.addAction(path)
            action.triggered.connect(
                lambda checked, p=path: open_recent(ui_we_want_to_set, p)
            )

    user_setting_dict["user_recent_images"] = valid_images

    if not valid_images:
        empty = image_menu.addAction("(Empty)")
        empty.setEnabled(False)


def handle_clear_recent(ui_we_want_to_set):
    clear_recent()
    rebuild_recent_menu(ui_we_want_to_set)


def open_recent(ui_we_want_to_set, path: str):

    if not Path(path).exists():
        return

    # 更新檔案樹定位
    if Path(path).is_dir():
        ui_we_want_to_set.model.setRootPath(path)
        ui_we_want_to_set.tree.setRootIndex(ui_we_want_to_set.model.index(path))
    else:
        parent = str(Path(path).parent)
        ui_we_want_to_set.model.setRootPath(parent)
        ui_we_want_to_set.tree.setRootIndex(ui_we_want_to_set.model.index(parent))

    ui_we_want_to_set.viewer.clear_tile_grid()
    open_path(main_gui=ui_we_want_to_set.viewer, path=path)

    if Path(path).is_dir():
        add_recent_folder(path)
        user_setting_dict["user_last_folder"] = path
    else:
        add_recent_image(path)
        user_setting_dict["user_last_folder"] = str(Path(path).parent)

    rebuild_recent_menu(ui_we_want_to_set)
