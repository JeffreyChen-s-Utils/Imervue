from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMenu

from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.recent_image import clear_recent, add_recent_folder, add_recent_image
from Imervue.user_settings.user_setting_dict import user_setting_dict


def build_recent_menu(ui_we_want_to_set, menu: QMenu):
    # ===== Recent =====
    lang = language_wrapper.language_word_dict
    recent_menu = menu.addMenu(lang.get("recent_menu_title", "Recent"))

    recent_folder_menu = recent_menu.addMenu(
        lang.get("recent_folders_title", "Recent Folders"),
    )
    recent_image_menu = recent_menu.addMenu(
        lang.get("recent_images_title", "Recent Images"),
    )

    ui_we_want_to_set._recent_folder_menu = recent_folder_menu
    ui_we_want_to_set._recent_image_menu = recent_image_menu
    ui_we_want_to_set._recent_menu = recent_menu

    recent_menu.addSeparator()

    clear_action = recent_menu.addAction(
        lang.get("recent_clear", "Clear Recent"),
    )
    clear_action.triggered.connect(
        lambda: handle_clear_recent(ui_we_want_to_set)
    )

    rebuild_recent_menu(ui_we_want_to_set)


def rebuild_recent_menu(ui_we_want_to_set):
    lang = language_wrapper.language_word_dict
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
            # Display the basename so the action stays scannable, but
            # surface the full path in the tooltip / status tip so the
            # user can disambiguate two folders with the same name.
            label = Path(path).name or path
            action = folder_menu.addAction(icon, label)
            action.setToolTip(path)
            action.setStatusTip(path)
            action.triggered.connect(
                lambda checked, p=path: open_recent(ui_we_want_to_set, p)
            )

    user_setting_dict["user_recent_folders"] = valid_folders

    if not valid_folders:
        empty = folder_menu.addAction(lang.get("recent_empty", "(Empty)"))
        empty.setEnabled(False)

    # ===== Images =====
    valid_images = []
    for path in user_setting_dict.get("user_recent_images", []):
        if Path(path).is_file():
            valid_images.append(path)

            label = Path(path).name or path
            action = image_menu.addAction(label)
            action.setToolTip(path)
            action.setStatusTip(path)
            action.triggered.connect(
                lambda checked, p=path: open_recent(ui_we_want_to_set, p)
            )

    user_setting_dict["user_recent_images"] = valid_images

    if not valid_images:
        empty = image_menu.addAction(lang.get("recent_empty", "(Empty)"))
        empty.setEnabled(False)
    # QMenu hides ``setToolTip`` content by default; flip the attribute
    # so artists actually see the full path on hover.
    folder_menu.setToolTipsVisible(True)
    image_menu.setToolTipsVisible(True)


def handle_clear_recent(ui_we_want_to_set):
    clear_recent()
    rebuild_recent_menu(ui_we_want_to_set)


def open_recent(ui_we_want_to_set, path: str):
    lang = language_wrapper.language_word_dict
    if not Path(path).exists():
        # Surface a toast so the user knows *why* the click did nothing,
        # then drop the stale entry from the recent list so the menu
        # self-heals.
        if hasattr(ui_we_want_to_set, "toast"):
            ui_we_want_to_set.toast.warning(
                lang.get(
                    "recent_missing", "{name} is no longer available",
                ).format(name=Path(path).name or path),
            )
        _drop_missing_recent(path)
        rebuild_recent_menu(ui_we_want_to_set)
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


def _drop_missing_recent(path: str) -> None:
    """Remove ``path`` from both the recent-folders and recent-images
    settings lists so the menu doesn't keep offering a dead link."""
    for key in ("user_recent_folders", "user_recent_images"):
        existing = user_setting_dict.get(key, [])
        if path in existing:
            user_setting_dict[key] = [p for p in existing if p != path]
