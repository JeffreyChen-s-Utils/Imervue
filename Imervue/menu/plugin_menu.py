"""
插件管理選單
Plugin management menu — view loaded plugins, download, enable/disable, open folder.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QTextEdit, QMenu,
)

from Imervue.gui.dialog_rows import confirm
from Imervue.gui.menu_tree import submenu_index, submenu_of
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.file_manager import reveal_in_file_manager
from Imervue.system.app_paths import plugins_dir as _plugins_dir

if TYPE_CHECKING:
    from PySide6.QtGui import QAction

    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.plugin.plugin_base import ImervuePlugin
    from Imervue.plugin.plugin_manager import PluginManager

# Object name of the Plugins menu. Reload looks the menu up by it instead of
# trusting a cached wrapper (see Imervue/gui/menu_tree.py).
PLUGIN_MENU_OBJECT_NAME = "plugin_menu"


def _get_plugin_dir() -> Path:
    return _plugins_dir()


# ===========================
# 選單建構
# ===========================

def build_plugin_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict

    plugin_menu = ui.menuBar().addMenu(
        lang.get("plugin_menu_title", "Plugins")
    )
    plugin_menu.setObjectName(PLUGIN_MENU_OBJECT_NAME)

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

    # 儲存參照，供 reload 和 plugin hook 使用
    ui._plugin_menu = plugin_menu

    return plugin_menu


# ===========================
# Entries added by plugins
# ===========================

def _address(obj) -> int:
    return shiboken6.getCppPointer(obj)[0]


def _menu_entries(ui: ImervueMainWindow) -> list[tuple[QMenu, QAction]]:
    """Every ``(container, action)`` pair in the menu bar and the menus under it."""
    bar = ui.menuBar()
    containers = [bar, *bar.findChildren(QMenu)]
    return [(container, action) for container in containers for action in container.actions()]


def dispatch_plugin_menus(ui: ImervueMainWindow, manager: PluginManager, plugin_menu) -> None:
    """Run every plugin's menu hook and remember the entries it added.

    Plugins may add to the Plugins menu, to an Extra Tools submenu or to the
    bar itself; the entries that were not there before the hooks ran are
    stored on ``ui`` so :func:`remove_plugin_menu_entries` can take exactly
    those out again on reload.
    """
    before = {(_address(c), _address(a)) for c, a in _menu_entries(ui)}
    manager.dispatch_build_menu_bar(plugin_menu)
    ui._plugin_menu_entries = [
        (container, action) for container, action in _menu_entries(ui)
        if (_address(container), _address(action)) not in before
    ]


def remove_plugin_menu_entries(ui: ImervueMainWindow) -> None:
    """Remove and delete the entries the last :func:`dispatch_plugin_menus` recorded.

    A plugin submenu is deleted with everything in it; plain actions are
    deleted as well, since their plugin instance is about to be unloaded.
    """
    entries = getattr(ui, "_plugin_menu_entries", [])
    index = submenu_index(ui.menuBar())
    for container, action in reversed(entries):
        if not (shiboken6.isValid(container) and shiboken6.isValid(action)):
            continue
        container.removeAction(action)
        sub = submenu_of(action, index)
        if sub is None:
            action.deleteLater()
            continue
        # Detach first: until the deferred delete runs the submenu would still
        # be a child, and a reloaded plugin that looks its shared submenu up
        # with findChildren (safety_review joins "AI Tools") would fill the
        # doomed one.
        sub.setParent(None)
        sub.deleteLater()
    ui._plugin_menu_entries = []


def _live_plugin_menu(ui: ImervueMainWindow):
    menu = ui.findChild(QMenu, PLUGIN_MENU_OBJECT_NAME)
    if menu is not None:
        return menu
    cached = getattr(ui, "_plugin_menu", None)
    return cached if cached is not None and shiboken6.isValid(cached) else None


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
            lang.get("plugin_info_version", "Version: {version}")
                .format(version=plugin.plugin_version),
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

    agreed = confirm(
        ui,
        lang.get("plugin_menu_reload", "Reload Plugins"),
        lang.get(
            "plugin_reload_confirm",
            "Reload all plugins? This will unload current plugins and re-discover them.",
        ),
    )
    if not agreed:
        return

    manager = ui.plugin_manager
    # Take the old entries out first: they would otherwise pile up and keep
    # calling the unloaded plugin instances.
    remove_plugin_menu_entries(ui)
    manager.unload_all()
    manager.discover_and_load()

    # 重新讓插件加到 Plugin 選單
    plugin_menu = _live_plugin_menu(ui)
    if plugin_menu is not None:
        dispatch_plugin_menus(ui, manager, plugin_menu)

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

    reveal_in_file_manager(str(plugin_dir), select=False)
