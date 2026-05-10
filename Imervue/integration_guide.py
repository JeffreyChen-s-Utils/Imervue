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

    # If plugins registered new languages, append them to the existing language menu.
    # The QMenu wrapper stored on ``main_window.language_menu`` can outlive its C++
    # peer in some PySide6 / Python combinations (same shiboken-teardown hazard
    # handled in ``Imervue_main_window._safe_submenus_of`` and
    # ``paint_workspace._safe_set_checked``); skip the plugin entries instead of
    # aborting plugin init when that happens.
    if language_wrapper.plugin_languages and hasattr(main_window, "language_menu"):
        _append_plugin_languages(main_window)

    # Let plugins contribute top-level tabs to the main window's tab strip.
    # ``_main_tabs`` is the QTabWidget owned by ImervueMainWindow that already
    # carries Imervue / Modify / Paint; plugin tabs append after Paint in
    # plugin discovery order. Each call is wrapped so a single bad plugin
    # can't tear down construction.
    tabs = getattr(main_window, "_main_tabs", None)
    if tabs is not None:
        _dispatch_main_tab_hook(manager, tabs)

    # Build the plugin management menu first, then let plugins add items into it
    plugin_menu = build_plugin_menu(main_window)
    manager.dispatch_build_menu_bar(plugin_menu)


def _dispatch_main_tab_hook(manager: PluginManager, tabs) -> None:
    """Walk loaded plugins and let each contribute a top-level tab.

    Same defensive pattern as ``_append_plugin_languages``: a RuntimeError
    from a stale shiboken wrapper or a buggy plugin is logged and skipped
    so the rest of plugin init keeps running.
    """
    for plugin in manager.plugins:
        try:
            plugin.on_build_main_tabs(tabs)
        except RuntimeError:
            logger.warning(
                "plugin %r raised RuntimeError in on_build_main_tabs; skipping",
                getattr(plugin, "plugin_name", type(plugin).__name__),
            )
        except Exception:  # noqa: BLE001 - plugin sandboxing
            logger.exception(
                "plugin %r raised in on_build_main_tabs",
                getattr(plugin, "plugin_name", type(plugin).__name__),
            )


def _append_plugin_languages(main_window: ImervueMainWindow) -> None:
    from Imervue.menu.language_menu import set_language
    from PySide6.QtGui import QAction
    menu = main_window.language_menu
    try:
        menu.addSeparator()
    except RuntimeError:
        logger.warning(
            "language_menu C++ wrapper already deleted; skipping plugin language entries"
        )
        return
    for lang_code, display_name in language_wrapper.plugin_languages.items():
        action = QAction(display_name, menu)
        action.triggered.connect(
            lambda _, code=lang_code: set_language(code, main_window)
        )
        try:
            menu.addAction(action)
        except RuntimeError:
            logger.warning(
                "language_menu wrapper went stale mid-append; stopping plugin language entries"
            )
            return
