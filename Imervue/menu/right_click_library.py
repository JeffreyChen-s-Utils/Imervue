"""Build query, event, image-info, bookmark, tag and album actions."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from Imervue.gui.tag_album_dialog import build_album_submenu
from Imervue.gui.tag_album_dialog import build_tag_submenu
from Imervue.image.info import get_image_info_at_pos
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.image.info import show_image_info_dialog
from Imervue.menu.right_click_current import _current_image_path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _query_search_action(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("query_search_menu", "Search by Query…"))
    action.triggered.connect(lambda: _open_query_search(main_gui))


def _open_query_search(main_gui: GPUImageView):
    from Imervue.gui.query_search import open_query_search

    open_query_search(main_gui)


def _events_action(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("events_menu", "Group into Events…"))
    action.triggered.connect(lambda: _open_events(main_gui))


def _open_events(main_gui: GPUImageView):
    from Imervue.gui.events_dialog import open_events

    open_events(main_gui)


def image_info_action(main_gui: GPUImageView, local_pos, menu: QMenu):
    info = get_image_info_at_pos(main_gui=main_gui, position=local_pos)
    if info:
        action = menu.addAction(
            language_wrapper.language_word_dict.get("right_click_menu_image_info")
        )
        action.triggered.connect(lambda: image_info(main_gui=main_gui, info=info))


def image_info(main_gui: GPUImageView, info):
    show_image_info_dialog(main_gui=main_gui, info=info)


def _bookmark_action(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    from Imervue.user_settings.bookmark import is_bookmarked

    if is_bookmarked(path):
        action = menu.addAction(lang.get("bookmark_remove_current", "Remove Bookmark"))
    else:
        action = menu.addAction(lang.get("bookmark_add_current", "Add Bookmark"))
    action.triggered.connect(lambda: main_gui._toggle_bookmark())


def _tag_album_actions(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    build_tag_submenu(main_gui, path, menu)
    build_album_submenu(main_gui, path, menu)
