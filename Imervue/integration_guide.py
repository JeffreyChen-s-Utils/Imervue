from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.menu.plugin_menu import build_plugin_menu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.pip_installer import register_translations as _register_pip_translations
from Imervue.plugin.plugin_manager import PluginManager

logger = logging.getLogger("Imervue.integration")


def _init_plugin_system_example(main_window: ImervueMainWindow) -> None:
    """Initialize the plugin system and load all discovered plugins.

    Called from ImervueMainWindow.__init__() after the UI is fully built.
    """
    # 註冊 pip 安裝對話框的翻譯（供所有插件共用）
    logger.info("Initializing plugin system")
    _register_pip_translations()

    manager = PluginManager(main_window)
    logger.info("Discovering and loading plugins...")
    manager.discover_and_load()
    logger.info("Plugin loading complete, %d plugin(s) loaded", len(manager.plugins))

    # Store on main_window so other parts of the app can access it
    main_window.plugin_manager = manager

    # If plugins registered new languages, append them to the existing language menu
    if language_wrapper.plugin_languages and hasattr(main_window, "language_menu"):
        from Imervue.menu.language_menu import set_language
        from PySide6.QtGui import QAction
        main_window.language_menu.addSeparator()
        for lang_code, display_name in language_wrapper.plugin_languages.items():
            action = QAction(display_name, main_window.language_menu)
            action.triggered.connect(
                lambda _, code=lang_code: set_language(code, main_window)
            )
            main_window.language_menu.addAction(action)

    # Build the plugin management menu first, then let plugins add items into it
    plugin_menu = build_plugin_menu(main_window)
    manager.dispatch_build_menu_bar(plugin_menu)
