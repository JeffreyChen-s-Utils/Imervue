"""
插件管理選單
Plugin management menu — view loaded plugins, download, enable/disable, open folder.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMenu, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QTextEdit,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.plugin.plugin_base import ImervuePlugin


def _get_plugin_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "plugins"


# ===========================
# 選單建構
# ===========================

def build_plugin_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict

    plugin_menu = ui.menuBar().addMenu(
        lang.get("plugin_menu_title", "Plugins")
    )

    # ===== 插件管理對話框 =====
    manage_action = plugin_menu.addAction(
        lang.get("plugin_menu_manage", "Manage Plugins")
    )
    manage_action.triggered.connect(lambda: _open_manage_dialog(ui))

    plugin_menu.addSeparator()

    # ===== 下載插件 =====
    download_action = plugin_menu.addAction(
        lang.get("plugin_menu_download", "Download Plugins")
    )
    download_action.triggered.connect(lambda: _open_download_dialog(ui))

    # ===== 開啟插件資料夾 =====
    open_folder_action = plugin_menu.addAction(
        lang.get("plugin_menu_open_folder", "Open Plugin Folder")
    )
    open_folder_action.triggered.connect(_open_plugin_folder)

    plugin_menu.addSeparator()

    # ===== 重新載入插件 =====
    reload_action = plugin_menu.addAction(
        lang.get("plugin_menu_reload", "Reload Plugins")
    )
    reload_action.triggered.connect(lambda: _reload_plugins(ui))

    return plugin_menu


# ===========================
# 插件管理對話框
# ===========================

class _PluginManageDialog(QDialog):
    """列出所有已載入插件，顯示詳細資訊，支援啟用/停用"""

    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._lang = language_wrapper.language_word_dict

        self.setWindowTitle(self._lang.get("plugin_menu_manage", "Manage Plugins"))
        self.setMinimumSize(600, 400)
        self._build_ui()

    def _build_ui(self):
        lang = self._lang
        layout = QVBoxLayout(self)

        # 標題
        count = 0
        if hasattr(self._ui, "plugin_manager"):
            count = len(self._ui.plugin_manager.plugins)
        header = QLabel(
            lang.get("plugin_manage_count", "{count} plugin(s) loaded").format(count=count)
        )
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(header)

        # 插件樹
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            lang.get("plugin_dl_col_name", "Plugin"),
            lang.get("plugin_info_version", "Version").split(":")[0].strip(),
            lang.get("plugin_info_author", "Author").split(":")[0].strip(),
        ])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self._tree)

        # 詳細資訊
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(120)
        self._detail.setPlaceholderText(
            lang.get("plugin_manage_select_hint", "Select a plugin to view details")
        )
        layout.addWidget(self._detail)

        # 按鈕列
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._close_btn = QPushButton(lang.get("plugin_dl_close", "Close"))
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

        self._populate()

    def _populate(self):
        self._tree.clear()
        if not hasattr(self._ui, "plugin_manager"):
            return

        for plugin in self._ui.plugin_manager.plugins:
            item = QTreeWidgetItem([
                plugin.plugin_name,
                plugin.plugin_version,
                plugin.plugin_author,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, plugin)
            self._tree.addTopLevelItem(item)

    def _on_selection(self):
        items = self._tree.selectedItems()
        if not items:
            self._detail.clear()
            return

        plugin: ImervuePlugin = items[0].data(0, Qt.ItemDataRole.UserRole)
        lang = self._lang

        lines = [
            lang.get("plugin_info_name", "Name: {name}").format(name=plugin.plugin_name),
            lang.get("plugin_info_version", "Version: {version}").format(version=plugin.plugin_version),
            lang.get("plugin_info_author", "Author: {author}").format(author=plugin.plugin_author),
            lang.get("plugin_info_description", "Description: {description}").format(
                description=plugin.plugin_description
            ),
        ]

        # 翻譯支援的語言
        translations = plugin.get_translations()
        if translations:
            supported = ", ".join(sorted(translations.keys()))
            lines.append(
                lang.get("plugin_info_languages", "Languages: {languages}").format(
                    languages=supported
                )
            )

        self._detail.setText("\n".join(lines))


# ===========================
# 動作函式
# ===========================

def _open_manage_dialog(ui: ImervueMainWindow):
    dlg = _PluginManageDialog(ui)
    dlg.exec()


def _show_plugin_info(ui: ImervueMainWindow, plugin):
    lang = language_wrapper.language_word_dict
    info_lines = [
        lang.get("plugin_info_name", "Name: {name}").format(name=plugin.plugin_name),
        lang.get("plugin_info_version", "Version: {version}").format(version=plugin.plugin_version),
        lang.get("plugin_info_author", "Author: {author}").format(author=plugin.plugin_author),
        lang.get("plugin_info_description", "Description: {description}").format(
            description=plugin.plugin_description
        ),
    ]
    QMessageBox.information(ui, plugin.plugin_name, "\n".join(info_lines))


def _open_download_dialog(ui: ImervueMainWindow):
    from Imervue.plugin.plugin_downloader import PluginDownloaderDialog
    dialog = PluginDownloaderDialog(ui)
    dialog.exec()


def _reload_plugins(ui: ImervueMainWindow):
    """卸載全部插件並重新載入"""
    lang = language_wrapper.language_word_dict

    if not hasattr(ui, "plugin_manager"):
        return

    reply = QMessageBox.question(
        ui,
        lang.get("plugin_menu_reload", "Reload Plugins"),
        lang.get(
            "plugin_reload_confirm",
            "Reload all plugins? This will unload current plugins and re-discover them.",
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    manager = ui.plugin_manager
    manager.unload_all()
    manager.discover_and_load()

    # 重新讓插件加選單
    manager.dispatch_build_menu_bar(ui.menuBar())

    loaded = len(manager.plugins)
    if hasattr(ui, "toast"):
        ui.toast.success(
            lang.get(
                "plugin_reload_done", "Reloaded {count} plugin(s)"
            ).format(count=loaded)
        )


def _open_plugin_folder():
    plugin_dir = _get_plugin_dir()
    plugin_dir.mkdir(exist_ok=True)

    if sys.platform == "win32":
        os.startfile(str(plugin_dir))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(plugin_dir)])
    else:
        subprocess.Popen(["xdg-open", str(plugin_dir)])
