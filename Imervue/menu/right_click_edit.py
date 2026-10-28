"""Build editing and deletion actions and apply lossless rotation."""

from __future__ import annotations

from Imervue.gui.modify_actions_widget import ModifyActionsWidget
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QWidgetAction
from Imervue.gpu_image_view.actions.delete import delete_current_image
from Imervue.gpu_image_view.actions.delete import delete_selected_tiles
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
from Imervue.menu.right_click_current import _current_image_path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _modify_submenu(main_gui: GPUImageView, menu: QMenu):
    """Add a "Modify" submenu whose single item is the shared
    :class:`ModifyActionsWidget` — same buttons (Develop / Annotate /
    Rotate CW/CCW / Flip H/V / Reset) as the menu-bar Modify menu.
    """
    if not main_gui.deep_zoom:
        return

    lang = language_wrapper.language_word_dict
    submenu = menu.addMenu(lang.get("modify_menu_title", "Modify"))
    widget_action = QWidgetAction(submenu)
    widget = ModifyActionsWidget(
        main_gui=main_gui,
        parent=submenu,
        on_triggered=menu.close,
    )
    widget_action.setDefaultWidget(widget)
    submenu.addAction(widget_action)


def _delete_action(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict

    if main_gui.tile_grid_mode and main_gui.tile_selection_mode:
        action = menu.addAction(lang.get("right_click_menu_delete_selected"))
        action.triggered.connect(lambda: delete_selected_tiles(main_gui))

    if main_gui.deep_zoom:
        action = menu.addAction(lang.get("right_click_menu_delete_current"))
        action.triggered.connect(lambda: delete_current_image(main_gui))


def _lossless_rotate_actions(main_gui: GPUImageView, menu: QMenu):
    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    sub = menu.addMenu(lang.get("right_click_lossless_rotate", "Lossless Rotate"))

    cw = sub.addAction(lang.get("lossless_rotate_cw", "Lossless Rotate CW"))
    cw.triggered.connect(lambda: _do_lossless_rotate(main_gui, path, clockwise=True))

    ccw = sub.addAction(lang.get("lossless_rotate_ccw", "Lossless Rotate CCW"))
    ccw.triggered.connect(lambda: _do_lossless_rotate(main_gui, path, clockwise=False))


def _do_lossless_rotate(main_gui: GPUImageView, path: str, clockwise: bool):
    lang = language_wrapper.language_word_dict
    ok = lossless_rotate(path, clockwise=clockwise)
    if ok:
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.info(
                lang.get("lossless_rotate_done", "Lossless rotation saved!")
            )
        # 重新載入圖片以反映旋轉
        from Imervue.gpu_image_view.images.image_loader import open_path

        main_gui._clear_deep_zoom()
        open_path(main_gui=main_gui, path=path)
    elif hasattr(main_gui.main_window, "toast"):
        main_gui.main_window.toast.info(
            lang.get("lossless_rotate_fail", "Lossless rotation failed")
        )
