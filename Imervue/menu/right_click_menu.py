from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu

from Imervue.gpu_image_view.actions.delete import delete_current_image, delete_selected_tiles
from Imervue.gpu_image_view.actions.select import switch_to_previous_image, switch_to_next_image
from Imervue.image.info import get_image_info_at_pos, show_image_info_dialog
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.menu.recent_menu import build_recent_menu

from pathlib import Path

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def right_click_context_menu(main_gui: GPUImageView, global_pos, local_pos):
    build_right_click_menu = QMenu(main_gui)

    go_to_parent_folder_action(main_gui=main_gui, menu=build_right_click_menu)
    switch_actions(main_gui=main_gui, menu=build_right_click_menu)
    delete_action(main_gui=main_gui, menu=build_right_click_menu)
    image_info_action(main_gui=main_gui, local_pos=local_pos, menu=build_right_click_menu)
    build_recent_menu(main_gui.main_window, build_right_click_menu)

    # Plugin hook: context menu
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_build_context_menu(build_right_click_menu, main_gui)

    if build_right_click_menu.actions():
        build_right_click_menu.exec(global_pos)


def switch_actions(main_gui: GPUImageView, menu: QMenu):
    if main_gui.deep_zoom:
        next_image_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_next_image"))
        next_image_action.triggered.connect(
            lambda: switch_to_next_image(main_gui=main_gui)
        )
        previous_image_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_previous_image")
        )
        previous_image_action.triggered.connect(
            lambda: switch_to_previous_image(main_gui=main_gui)
        )


def delete_action(main_gui: GPUImageView, menu: QMenu):
    if main_gui.tile_grid_mode and main_gui.tile_selection_mode:
        delete_selected_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_delete_selected"))
        delete_selected_action.triggered.connect(lambda: delete_selected_tiles(main_gui=main_gui))
    if main_gui.deep_zoom:
        delete_current_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_delete_current"))
        delete_current_action.triggered.connect(lambda: delete_current_image(main_gui=main_gui))


def go_to_parent_folder_action(main_gui: GPUImageView, menu: QMenu):
    # ===== 回到上層資料夾 =====
    if main_gui.model.images:
        current_path = None
        if main_gui.deep_zoom:
            current_path = main_gui.model.images[main_gui.current_index]
        elif main_gui.tile_grid_mode:
            # 取目前資料夾
            current_path = main_gui.model.images[0]

        if current_path:
            parent_folder = Path(current_path).parent.parent

            if parent_folder.exists():
                action = menu.addAction(
                    language_wrapper.language_word_dict.get("right_click_menu_go_to_parent_folder"))
                action.triggered.connect(
                    lambda: jump_to_folder(main_gui=main_gui, folder_path=parent_folder)
                )


def jump_to_folder(main_gui: GPUImageView, folder_path: Path):
    model = main_gui.main_window.model
    tree = main_gui.main_window.tree

    index = model.index(str(folder_path))
    if index.isValid():
        tree.setCurrentIndex(index)
        tree.scrollTo(index)
        tree.setRootIndex(index)


def image_info_action(main_gui: GPUImageView, local_pos, menu: QMenu):
    info = get_image_info_at_pos(main_gui=main_gui, position=local_pos)
    if info:
        action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_image_info")
        )
        action.triggered.connect(
            lambda: image_info(main_gui=main_gui, info=info)
        )


def image_info(main_gui: GPUImageView, info):
    show_image_info_dialog(main_gui=main_gui, info=info)