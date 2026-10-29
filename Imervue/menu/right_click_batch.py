"""Build batch commands with trigger-time selection evaluation."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from Imervue.gpu_image_view.actions.batch_ops import batch_rotate
from Imervue.gui.tag_album_dialog import build_batch_tag_album_submenu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.gui.batch_export_dialog import open_batch_export
from Imervue.gpu_image_view.actions.batch_ops import open_batch_move
from Imervue.gpu_image_view.actions.batch_ops import open_batch_rename
from Imervue.gui.gif_video_dialog import open_gif_video_dialog
from Imervue.menu.right_click_metadata import _auto_cull_blurry
from Imervue.menu.right_click_metadata import _auto_cull_low_quality
from Imervue.menu.right_click_metadata import _auto_orient
from Imervue.menu.right_click_pages import _combine_multipage
from Imervue.menu.right_click_metadata import _import_by_date
from Imervue.menu.right_click_metadata import _index_keywords
from Imervue.menu.right_click_metadata import _tag_by_location
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _batch_actions(main_gui: GPUImageView, menu: QMenu):
    if not (main_gui.tile_grid_mode and main_gui.tile_selection_mode and main_gui.selected_tiles):
        return
    lang = language_wrapper.language_word_dict
    batch_menu = menu.addMenu(lang.get("right_click_batch", "Batch Operations"))

    rename_action = batch_menu.addAction(lang.get("batch_rename_title", "Batch Rename"))
    rename_action.triggered.connect(lambda: open_batch_rename(main_gui))

    move_action = batch_menu.addAction(lang.get("batch_move_title", "Move / Copy"))
    move_action.triggered.connect(lambda: open_batch_move(main_gui))

    rot_cw = batch_menu.addAction(lang.get("batch_rotate_cw", "Rotate All CW"))
    rot_cw.triggered.connect(lambda: batch_rotate(main_gui, list(main_gui.selected_tiles), 90))

    rot_ccw = batch_menu.addAction(lang.get("batch_rotate_ccw", "Rotate All CCW"))
    rot_ccw.triggered.connect(lambda: batch_rotate(main_gui, list(main_gui.selected_tiles), -90))

    batch_menu.addSeparator()

    export_action = batch_menu.addAction(lang.get("batch_export_title", "Batch Export"))
    export_action.triggered.connect(lambda: open_batch_export(main_gui))

    gif_action = batch_menu.addAction(lang.get("gif_video_title", "Create GIF / Video"))
    gif_action.triggered.connect(lambda: open_gif_video_dialog(main_gui))

    geo_action = batch_menu.addAction(lang.get("batch_geo_keywords", "Tag by Location"))
    geo_action.triggered.connect(lambda: _tag_by_location(main_gui))

    index_action = batch_menu.addAction(lang.get("batch_index_keywords", "Index Keywords"))
    index_action.triggered.connect(lambda: _index_keywords(main_gui))

    cull_action = batch_menu.addAction(lang.get("batch_auto_cull", "Auto-cull Blurry"))
    cull_action.triggered.connect(lambda: _auto_cull_blurry(main_gui))

    quality_action = batch_menu.addAction(lang.get("batch_quality_cull", "Auto-cull Low Quality"))
    quality_action.triggered.connect(lambda: _auto_cull_low_quality(main_gui))

    orient_action = batch_menu.addAction(lang.get("batch_auto_orient", "Auto-Rotate by EXIF"))
    orient_action.triggered.connect(lambda: _auto_orient(main_gui))

    combine_action = batch_menu.addAction(lang.get("multipage_combine", "Combine to PDF / TIFF…"))
    combine_action.triggered.connect(lambda: _combine_multipage(main_gui))

    date_import_action = batch_menu.addAction(
        lang.get("date_import_menu", "Import to Dated Folders…")
    )
    date_import_action.triggered.connect(lambda: _import_by_date(main_gui))

    build_batch_tag_album_submenu(main_gui, list(main_gui.selected_tiles), batch_menu)
