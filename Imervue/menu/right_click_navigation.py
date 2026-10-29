"""Build image navigation, parent-folder, comparison and slideshow actions."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QMenu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.gpu_image_view.actions.compare_dialog import open_compare_dialog
from Imervue.gpu_image_view.actions.slideshow import open_slideshow_dialog
from Imervue.gpu_image_view.actions.select import switch_to_next_image
from Imervue.gpu_image_view.actions.select import switch_to_previous_image
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _slideshow_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.model.images or len(main_gui.model.images) < 2:
        return
    lang = language_wrapper.language_word_dict

    if hasattr(main_gui, "_slideshow") and main_gui._slideshow and main_gui._slideshow.running:
        action = menu.addAction(lang.get("right_click_slideshow_stop", "Stop Slideshow"))
        action.triggered.connect(lambda: main_gui._slideshow.stop())
    else:
        action = menu.addAction(lang.get("right_click_slideshow", "Slideshow"))
        action.triggered.connect(lambda: open_slideshow_dialog(main_gui))


def _compare_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.model.images or len(main_gui.model.images) < 2:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("right_click_compare", "Compare Images"))
    action.triggered.connect(lambda: open_compare_dialog(main_gui))


def switch_actions(main_gui: GPUImageView, menu: QMenu):
    if main_gui.deep_zoom:
        next_image_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_next_image")
        )
        next_image_action.triggered.connect(lambda: switch_to_next_image(main_gui=main_gui))
        previous_image_action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_previous_image")
        )
        previous_image_action.triggered.connect(lambda: switch_to_previous_image(main_gui=main_gui))


def go_to_parent_folder_action(main_gui: GPUImageView, menu: QMenu):
    images = main_gui.model.images
    if images:
        current_path = None
        if main_gui.deep_zoom and 0 <= main_gui.current_index < len(images):
            current_path = images[main_gui.current_index]
        elif main_gui.tile_grid_mode:
            current_path = images[0]

        if current_path:
            parent_folder = Path(current_path).parent.parent

            if parent_folder.exists():
                action = menu.addAction(
                    language_wrapper.language_word_dict.get("right_click_menu_go_to_parent_folder")
                )
                action.triggered.connect(
                    lambda: jump_to_folder(main_gui=main_gui, folder_path=parent_folder)
                )


def jump_to_folder(main_gui: GPUImageView, folder_path: Path):
    model = main_gui.main_window.model
    tree = main_gui.main_window.tree

    index = model.index(str(folder_path))
    if index.isValid():
        tree.set_root_path(str(folder_path))
