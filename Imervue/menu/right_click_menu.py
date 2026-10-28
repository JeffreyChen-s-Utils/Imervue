"""Compose the ordered context menu and preserve action entry points."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from Imervue.menu.recent_menu import build_recent_menu
from Imervue.menu.right_click_batch import _batch_actions
from Imervue.menu.right_click_library import _bookmark_action
from Imervue.menu.right_click_navigation import _compare_action
from Imervue.menu.right_click_current import _copy_image_action
from Imervue.menu.right_click_current import _copy_path_action
from Imervue.menu.right_click_edit import _delete_action
from Imervue.menu.right_click_library import _events_action
from Imervue.menu.right_click_current import _export_action
from Imervue.menu.right_click_extra import _extra_tools_submenu
from Imervue.menu.right_click_edit import _lossless_rotate_actions
from Imervue.menu.right_click_maintenance import _maintenance_action
from Imervue.menu.right_click_edit import _modify_submenu
from Imervue.menu.right_click_current import _ocr_action
from Imervue.menu.right_click_library import _query_search_action
from Imervue.menu.right_click_recovery import _relocate_missing_action
from Imervue.menu.right_click_recovery import _retry_load_action
from Imervue.menu.right_click_current import _set_wallpaper_action
from Imervue.menu.right_click_current import _show_in_explorer_action
from Imervue.menu.right_click_navigation import _slideshow_action
from Imervue.menu.right_click_pages import _split_pages_action
from Imervue.menu.right_click_maintenance import _staging_tray_actions
from Imervue.menu.right_click_library import _tag_album_actions
from Imervue.menu.right_click_navigation import go_to_parent_folder_action
from Imervue.menu.right_click_library import image_info_action
from Imervue.menu.right_click_navigation import switch_actions
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView
from Imervue.menu.right_click_maintenance import _add_to_staging_tray
from Imervue.menu.right_click_metadata import _auto_cull_blurry
from Imervue.menu.right_click_metadata import _auto_cull_low_quality
from Imervue.menu.right_click_metadata import _auto_orient
from Imervue.menu.right_click_pages import _combine_multipage
from Imervue.menu.right_click_current import _current_image_path
from Imervue.menu.right_click_extra import _do_batch_convert
from Imervue.menu.right_click_extra import _do_duplicate_detection
from Imervue.menu.right_click_extra import _do_exif_strip
from Imervue.menu.right_click_extra import _do_image_organizer
from Imervue.menu.right_click_extra import _do_image_sanitize
from Imervue.menu.right_click_edit import _do_lossless_rotate
from Imervue.menu.right_click_extra import _do_upscale_batch
from Imervue.menu.right_click_extra import _do_upscale_single
from Imervue.menu.right_click_metadata import _import_by_date
from Imervue.menu.right_click_metadata import _index_keywords
from Imervue.menu.right_click_maintenance import _library_maintenance
from Imervue.menu.right_click_library import _open_events
from Imervue.menu.right_click_current import _open_ocr
from Imervue.menu.right_click_library import _open_query_search
from Imervue.menu.right_click_maintenance import _open_staging_tray
from Imervue.menu.right_click_recovery import _relocate_missing
from Imervue.menu.right_click_recovery import _retry_load
from Imervue.menu.right_click_pages import _split_multipage
from Imervue.menu.right_click_metadata import _tag_by_location
from Imervue.menu.right_click_library import image_info
from Imervue.menu.right_click_navigation import jump_to_folder

__all__ = [
    "_add_to_staging_tray",
    "_auto_cull_blurry",
    "_auto_cull_low_quality",
    "_auto_orient",
    "_batch_actions",
    "_bookmark_action",
    "_combine_multipage",
    "_compare_action",
    "_copy_image_action",
    "_copy_path_action",
    "_current_image_path",
    "_delete_action",
    "_do_batch_convert",
    "_do_duplicate_detection",
    "_do_exif_strip",
    "_do_image_organizer",
    "_do_image_sanitize",
    "_do_lossless_rotate",
    "_do_upscale_batch",
    "_do_upscale_single",
    "_events_action",
    "_export_action",
    "_extra_tools_submenu",
    "_import_by_date",
    "_index_keywords",
    "_library_maintenance",
    "_lossless_rotate_actions",
    "_maintenance_action",
    "_modify_submenu",
    "_ocr_action",
    "_open_events",
    "_open_ocr",
    "_open_query_search",
    "_open_staging_tray",
    "_query_search_action",
    "_relocate_missing",
    "_relocate_missing_action",
    "_retry_load",
    "_retry_load_action",
    "_set_wallpaper_action",
    "_show_in_explorer_action",
    "_slideshow_action",
    "_split_multipage",
    "_split_pages_action",
    "_staging_tray_actions",
    "_tag_album_actions",
    "_tag_by_location",
    "go_to_parent_folder_action",
    "image_info",
    "image_info_action",
    "jump_to_folder",
    "right_click_context_menu",
    "switch_actions",
]


def right_click_context_menu(main_gui: GPUImageView, global_pos, local_pos):
    build_right_click_menu = QMenu(main_gui)

    go_to_parent_folder_action(main_gui=main_gui, menu=build_right_click_menu)
    switch_actions(main_gui=main_gui, menu=build_right_click_menu)

    build_right_click_menu.addSeparator()

    # === 新增快速操作 ===
    _show_in_explorer_action(main_gui, build_right_click_menu)
    _copy_path_action(main_gui, build_right_click_menu)
    _relocate_missing_action(main_gui, build_right_click_menu)
    _retry_load_action(main_gui, build_right_click_menu)
    _copy_image_action(main_gui, build_right_click_menu)
    _ocr_action(main_gui, build_right_click_menu)
    _split_pages_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _modify_submenu(main_gui, build_right_click_menu)
    _batch_actions(main_gui, build_right_click_menu)
    _staging_tray_actions(main_gui, build_right_click_menu)
    _delete_action(main_gui, build_right_click_menu)
    _set_wallpaper_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _compare_action(main_gui, build_right_click_menu)
    _slideshow_action(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _export_action(main_gui, build_right_click_menu)
    _lossless_rotate_actions(main_gui, build_right_click_menu)
    _extra_tools_submenu(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _bookmark_action(main_gui, build_right_click_menu)
    _tag_album_actions(main_gui, build_right_click_menu)

    build_right_click_menu.addSeparator()

    _query_search_action(main_gui, build_right_click_menu)
    _events_action(main_gui, build_right_click_menu)
    _maintenance_action(main_gui, build_right_click_menu)
    image_info_action(main_gui=main_gui, local_pos=local_pos, menu=build_right_click_menu)
    # store_refs=False: this throwaway context menu must not rebind the main
    # window's cached Recent submenu handles, or the File menu's Recent lists
    # freeze (every later rebuild would target these dismissed submenus).
    build_recent_menu(main_gui.main_window, build_right_click_menu, store_refs=False)

    # Plugin hook: context menu
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_build_context_menu(
            build_right_click_menu, main_gui
        )

    if build_right_click_menu.actions():
        build_right_click_menu.exec(global_pos)
