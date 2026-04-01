from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def build_language_menu(ui_we_want_to_set: ImervueMainWindow):
    """
    建立語言選單
    Build the language menu for the main UI
    """
    language_menu = ui_we_want_to_set.menuBar().addMenu(
        language_wrapper.language_word_dict.get("menu_bar_language")
    )
    ui_we_want_to_set.language_menu = language_menu

    # 內建語言清單 (label_key, 語言代碼)
    builtin_languages = [
        ("language_menu_bar_english", "English"),
        ("language_menu_bar_traditional_chinese", "Traditional_Chinese"),
        ("language_menu_bar_chinese", "Chinese"),
        ("language_menu_bar_koren", "Korean"),
        ("language_menu_bar_japanese", "Japanese"),
    ]

    # 動態建立內建語言 QAction
    for label_key, lang_code in builtin_languages:
        action = QAction(language_wrapper.language_word_dict.get(label_key), language_menu)
        action.triggered.connect(lambda _, code=lang_code: set_language(code, ui_we_want_to_set))
        language_menu.addAction(action)

    return language_menu


def set_language(language: str, ui_we_want_to_set: ImervueMainWindow) -> None:
    """
    設定語言並提示使用者重新啟動
    Set application language and prompt user to restart
    """
    user_setting_dict.update({"language": language})

    message_box = QMessageBox(ui_we_want_to_set)
    message_box.setText(language_wrapper.language_word_dict.get("language_menu_bar_please_restart_messagebox"))
    message_box.exec()  # 使用 exec() 讓使用者必須確認