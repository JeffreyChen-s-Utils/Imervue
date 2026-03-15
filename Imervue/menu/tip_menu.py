from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def build_tip_menu(ui_we_want_to_set: ImervueMainWindow):
    # ===== 主 Tip 選單 =====
    tip_menu = ui_we_want_to_set.menuBar().addMenu(
        language_wrapper.language_word_dict.get("main_window_tip_menu", "Tip")
    )

    # ==========================
    # 滑鼠說明子選單
    # ==========================
    mouse_menu = tip_menu.addMenu(
        language_wrapper.language_word_dict.get("main_window_mouse_tip_menu", "Mouse")
    )

    mouse_keys = [
        "mouse_control_middle_tip",
        "mouse_control_left_tip",
        "mouse_control_multi_select_tip",
    ]

    for key in mouse_keys:
        text = language_wrapper.language_word_dict.get(key)
        action = mouse_menu.addAction(text)
        action.setEnabled(False)
        mouse_menu.addSeparator()

    # 主選單分隔線
    tip_menu.addSeparator()

    # ==========================
    # 鍵盤說明子選單
    # ==========================
    keyboard_menu = tip_menu.addMenu(
        language_wrapper.language_word_dict.get("main_window_keyboard_tip_menu", "Keyboard")
    )

    keyboard_keys = [
        "keyboard_control_esc_tip",
        "keyboard_control_tile_arrow_up_tip",
        "keyboard_control_tile_arrow_down_tip",
        "keyboard_control_tile_arrow_left_tip",
        "keyboard_control_tile_arrow_right_tip",
        "keyboard_control_delete_tip",
        "keyboard_r_tip"
    ]

    for i, key in enumerate(keyboard_keys):
        text = language_wrapper.language_word_dict.get(key)
        action = keyboard_menu.addAction(text)
        action.setEnabled(False)
        keyboard_menu.addSeparator()

    return tip_menu
