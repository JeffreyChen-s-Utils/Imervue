from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from PySide6.QtWidgets import QMenu

from Imervue.menu.language_menu import LANGUAGE_MENU_OBJECT_NAME
from Imervue.menu.plugin_menu import build_plugin_menu, dispatch_plugin_menus
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
    # The QMenu wrapper stored on ``main_window.language_menu`` goes stale once
    # anything walks the menus with ``QAction.menu()`` (Imervue/gui/menu_tree.py),
    # so the menu is re-resolved by object name; if it still cannot be reached the
    # plugin entries are skipped instead of aborting plugin init.
    if language_wrapper.plugin_languages and hasattr(main_window, "language_menu"):
        _append_plugin_languages(main_window)

    # Let plugins contribute top-level tabs to the main window's tab strip.
    # ``_main_tabs`` is the QTabWidget owned by ImervueMainWindow that already
    # carries Imervue / Modify / Paint / Puppet / Desktop Pet; plugin tabs
    # append after Desktop Pet in plugin discovery order. Each call is
    # wrapped so a single bad plugin can't tear down construction.
    tabs = getattr(main_window, "_main_tabs", None)
    if tabs is not None:
        _dispatch_main_tab_hook(manager, tabs)

    # Build the plugin management menu first, then let plugins add items into it
    # (recording them so Reload Plugins can take them out again).
    plugin_menu = build_plugin_menu(main_window)
    dispatch_plugin_menus(main_window, manager, plugin_menu)


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
        except Exception:  # plugin sandboxing
            logger.exception(
                "plugin %r raised in on_build_main_tabs",
                getattr(plugin, "plugin_name", type(plugin).__name__),
            )


def _append_plugin_languages(main_window: ImervueMainWindow) -> None:
    from Imervue.menu.language_menu import set_language
    from PySide6.QtGui import QAction
    menu = _resolve_language_menu(main_window)
    if menu is None:
        logger.warning(
            "language menu not reachable; plugin languages %s are not listed",
            sorted(language_wrapper.plugin_languages),
        )
        return
    main_window.language_menu = menu
    try:
        menu.addSeparator()
    except RuntimeError:
        logger.warning("language menu went stale; plugin languages are not listed")
        return
    for lang_code, display_name in language_wrapper.plugin_languages.items():
        action = QAction(display_name, menu)
        action.triggered.connect(
            lambda _, code=lang_code: set_language(code, main_window)
        )
        try:
            menu.addAction(action)
        except RuntimeError:
            logger.warning("language menu went stale mid-append; stopping plugin languages")
            return


def _resolve_language_menu(main_window: ImervueMainWindow):
    """Return a live Language :class:`QMenu`, or ``None``.

    The cached ``main_window.language_menu`` is used while its wrapper is
    valid. Otherwise the menu is found by the object name
    ``build_language_menu`` gives it, and failing that by its localised title
    among the window's menus. It is never looked up through
    ``QAction.menu()``, which is what invalidates the cached wrapper in the
    first place (Imervue/gui/menu_tree.py).
    """
    cached = _verify_alive(getattr(main_window, "language_menu", None))
    if cached is not None:
        return cached
    named = _verify_alive(main_window.findChild(QMenu, LANGUAGE_MENU_OBJECT_NAME))
    if named is not None:
        return named
    expected_title = language_wrapper.language_word_dict.get(
        "menu_bar_language", "Language",
    )
    for menu in main_window.findChildren(QMenu):
        if _verify_alive(menu) is not None and menu.title().replace("&", "") == expected_title:
            return menu
    return None


def _verify_alive(menu):
    """Return ``menu`` only if its C++ peer answers a cheap method
    without raising — anything else returns ``None`` so the caller
    can take the skip path."""
    if menu is None:
        return None
    try:
        menu.actions()
    except RuntimeError:
        return None
    return menu
