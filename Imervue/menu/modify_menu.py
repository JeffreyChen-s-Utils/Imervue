"""Deep Zoom 專用的「修改」選單動作。

僅在使用者進入 DeepZoom 模式檢視單張圖片時出現。點擊後直接打開
DevelopPanel（整合了註解、旋轉、翻轉、顯影調整、重設等所有修改功能）。

選單動作在建立時隱藏，由 ``GPUImageView.load_deep_zoom_image`` 顯示、
``_clear_deep_zoom`` 隱藏，避免在 tile grid 模式下出現毫無作用的入口。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def build_modify_menu(ui_we_want_to_set: ImervueMainWindow):
    """Build a single Modify action on the menu bar that opens the panel."""
    lang = language_wrapper.language_word_dict

    action = QAction(lang.get("modify_menu_title", "Modify"), ui_we_want_to_set)
    action.triggered.connect(lambda: ui_we_want_to_set.viewer.open_develop_panel())
    action.setVisible(False)
    ui_we_want_to_set.menuBar().addAction(action)
    ui_we_want_to_set._modify_menu_action = action
