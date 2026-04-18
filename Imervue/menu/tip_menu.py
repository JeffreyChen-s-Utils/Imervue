"""
操作說明選單 + 快捷鍵一覽對話框
Instructions menu with a shortcut cheat-sheet dialog.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QWidget, QGridLayout, QScrollArea, QPushButton, QFrame,
    QSizePolicy,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


# ===========================
# 快捷鍵定義
# ===========================

def _mouse_shortcuts() -> list[tuple[str, str]]:
    """(shortcut_key, lang_key)"""
    return [
        ("tip_mouse_middle", "mouse_control_middle_tip"),
        ("tip_mouse_left_click", "mouse_control_left_tip"),
        ("tip_mouse_left_drag", "mouse_control_multi_select_tip"),
        ("tip_mouse_right", "tip_mouse_right_desc"),
        ("tip_mouse_scroll", "tip_mouse_scroll_desc"),
    ]


def _keyboard_shortcuts() -> list[tuple[str, str]]:
    # Ordered so related shortcuts cluster: core → rating/label → navigation
    # → view modes → advanced → animation. Keep this in sync with
    # DEFAULT_SHORTCUTS in shortcut_settings_dialog.py.
    return [
        # --- Core ---
        ("Esc", "keyboard_control_esc_tip"),
        ("F", "keyboard_f_tip"),
        ("R / Shift+R", "keyboard_r_tip"),
        ("Home", "keyboard_home_tip"),
        ("E", "keyboard_e_tip"),
        ("S", "keyboard_slideshow_tip"),
        ("T", "keyboard_t_tip"),
        ("H", "keyboard_h_tip"),
        ("W / Shift+W", "keyboard_w_tip"),
        ("B", "keyboard_b_tip"),
        ("Delete", "keyboard_control_delete_tip"),
        ("Ctrl+C", "keyboard_ctrl_c_tip"),
        ("Ctrl+V", "keyboard_ctrl_v_tip"),
        ("Ctrl+Z", "keyboard_undo_tip"),
        ("Ctrl+Shift+Z", "keyboard_redo_tip"),
        ("Ctrl+F  /  /", "keyboard_search_tip"),
        # --- Rating + colour labels ---
        ("1 ~ 5", "keyboard_rating_tip"),
        ("0", "keyboard_favorite_tip"),
        ("F1 ~ F5", "keyboard_color_label_tip"),
        # --- Navigation ---
        ("\u2190 \u2192", "keyboard_arrow_lr_tip"),
        ("\u2191 \u2193 \u2190 \u2192", "keyboard_arrow_tile_tip"),
        ("Ctrl+Shift+\u2190 / \u2192", "keyboard_cross_folder_tip"),
        ("Alt+\u2190 / \u2192", "keyboard_history_tip"),
        ("Ctrl+G", "keyboard_goto_tip"),
        ("X", "keyboard_random_tip"),
        # --- View modes ---
        ("Shift+Tab", "keyboard_theater_tip"),
        ("Ctrl+L", "keyboard_list_mode_tip"),
        ("Shift+S", "keyboard_split_view_tip"),
        ("Shift+D  /  Ctrl+Shift+D", "keyboard_dual_page_tip"),
        ("Ctrl+Shift+M", "keyboard_multi_monitor_tip"),
        # --- Advanced overlays ---
        ("F8  /  Ctrl+F8", "keyboard_osd_tip"),
        ("Shift+P", "keyboard_pixel_view_tip"),
        ("Shift+M", "keyboard_color_mode_tip"),
        # --- Animation ---
        ("Space", "keyboard_anim_play_tip"),
        (",  /  .", "keyboard_anim_frame_tip"),
        ("[  /  ]", "keyboard_anim_speed_tip"),
    ]


# ===========================
# 對話框
# ===========================

class ShortcutDialog(QDialog):
    """快捷鍵 & 操作說明對話框"""

    def __init__(self, parent: ImervueMainWindow):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("main_window_tip_menu", "Instructions"))
        self.setMinimumSize(560, 440)

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ===== 滑鼠頁籤 =====
        mouse_tab = self._build_tab(_mouse_shortcuts(), lang)
        tabs.addTab(mouse_tab, lang.get("main_window_mouse_tip_menu", "Mouse"))

        # ===== 鍵盤頁籤 =====
        keyboard_tab = self._build_tab(_keyboard_shortcuts(), lang)
        tabs.addTab(keyboard_tab, lang.get("main_window_keyboard_tip_menu", "Keyboard"))

        # 關閉按鈕
        close_btn = QPushButton(lang.get("tip_close", "Close"))
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _build_tab(shortcuts: list[tuple[str, str]], lang: dict) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setSpacing(0)
        grid.setContentsMargins(12, 8, 12, 8)

        for row, (shortcut, desc_key) in enumerate(shortcuts):
            # 快捷鍵標籤（帶底色）
            key_label = QLabel(shortcut)
            key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_label.setStyleSheet(
                "QLabel {"
                "  background: #3a3a3a; color: #e0e0e0;"
                "  border: 1px solid #555; border-radius: 4px;"
                "  padding: 4px 10px; font-family: 'Consolas', 'Courier New', monospace;"
                "  font-size: 13px; font-weight: bold;"
                "}"
            )
            key_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            # 說明文字
            desc_text = lang.get(desc_key, desc_key)
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                "QLabel { padding: 6px 12px; font-size: 13px; color: #ccc; }"
            )

            grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(desc_label, row, 1, Qt.AlignmentFlag.AlignVCenter)

            # 分隔線
            if row < len(shortcuts) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet("QFrame { color: #333; }")
                grid.addWidget(line, row, 0, 1, 2,
                               Qt.AlignmentFlag.AlignBottom)

        grid.setRowStretch(len(shortcuts), 1)
        scroll.setWidget(container)
        return scroll


# ===========================
# 選單入口
# ===========================

def build_tip_menu(ui_we_want_to_set: ImervueMainWindow):
    tip_menu = ui_we_want_to_set.menuBar().addMenu(
        language_wrapper.language_word_dict.get("main_window_tip_menu", "Instructions")
    )

    action = tip_menu.addAction(
        language_wrapper.language_word_dict.get("tip_show_shortcuts", "Keyboard & Mouse Shortcuts")
    )
    action.triggered.connect(lambda: _show_dialog(ui_we_want_to_set))

    return tip_menu


def _show_dialog(ui: ImervueMainWindow):
    dlg = ShortcutDialog(ui)
    dlg.exec()
