from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMenu, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def build_plugin_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict

    plugin_menu = ui.menuBar().addMenu(lang.get("plugin_menu_title", "Plugins"))

    # ===== Loaded Plugins submenu =====
    loaded_menu = plugin_menu.addMenu(lang.get("plugin_menu_loaded", "Loaded Plugins"))

    if hasattr(ui, "plugin_manager") and ui.plugin_manager.plugins:
        for plugin in ui.plugin_manager.plugins:
            action = loaded_menu.addAction(f"{plugin.plugin_name} v{plugin.plugin_version}")
            action.triggered.connect(
                lambda checked, p=plugin: _show_plugin_info(ui, p)
            )
    else:
        no_plugins = loaded_menu.addAction(lang.get("plugin_menu_no_plugins", "No plugins loaded"))
        no_plugins.setEnabled(False)

    plugin_menu.addSeparator()

    # ===== Download Plugins =====
    download_action = plugin_menu.addAction(lang.get("plugin_menu_download", "Download Plugins"))
    download_action.triggered.connect(lambda: _open_download_dialog(ui))

    # ===== Open Plugin Folder =====
    open_folder_action = plugin_menu.addAction(lang.get("plugin_menu_open_folder", "Open Plugin Folder"))
    open_folder_action.triggered.connect(lambda: _open_plugin_folder())

    return plugin_menu


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


def _open_plugin_folder():
    project_root = Path(__file__).resolve().parent.parent.parent
    plugin_dir = project_root / "plugins"
    plugin_dir.mkdir(exist_ok=True)

    if sys.platform == "win32":
        os.startfile(str(plugin_dir))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(plugin_dir)])
    else:
        subprocess.Popen(["xdg-open", str(plugin_dir)])
