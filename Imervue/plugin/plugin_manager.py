from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.plugin_discovery import _plugin_classes, _register_languages_of
from Imervue.plugin.plugin_dispatch import PluginDispatchMixin
from Imervue.plugin.status import status_registry
from Imervue.system.app_paths import plugins_dir as _plugins_dir

logger = logging.getLogger("Imervue.plugin")


class PluginManager(PluginDispatchMixin):
    """Discovers, loads, and manages Imervue plugins.

    Plugins are Python packages placed in the ``plugins/`` directory
    (next to the Imervue package). Each plugin package must contain an
    ``__init__.py`` that defines a ``plugin_class`` attribute pointing to
    a subclass of :class:`ImervuePlugin`.

    Example plugin structure::

        plugins/
            my_plugin/
                __init__.py   # must set: plugin_class = MyPlugin
                my_plugin.py  # contains class MyPlugin(ImervuePlugin)
    """

    def __init__(self, main_window: ImervueMainWindow):
        self.status_scope = f"window:{id(self)}"
        self.main_window = main_window
        self._plugins: list[ImervuePlugin] = []
        self._plugin_dirs: list[Path] = []
        self._pet_hook_connected = False

    @property
    def plugins(self) -> list[ImervuePlugin]:
        return list(self._plugins)

    # ===========================
    # Discovery & Loading
    # ===========================

    def discover_and_load(self, plugin_dirs: list[Path] | None = None) -> None:
        """Discover and load plugins from plugin directories.

        Args:
            plugin_dirs: List of directories to scan. If None, uses the
                default ``plugins/`` directory next to the Imervue package.
        """
        if plugin_dirs is None:
            plugin_dirs = [_plugins_dir()]

        self._plugin_dirs = plugin_dirs

        for plugin_class in _plugin_classes(plugin_dirs, scope=self.status_scope):
            self._instantiate(plugin_class)

    def _instantiate(self, plugin_class: type[ImervuePlugin]) -> None:
        """Instantiate ``plugin_class`` once, run ``on_plugin_loaded`` and merge its strings."""
        for existing in self._plugins:
            if type(existing).__name__ == plugin_class.__name__:
                logger.warning(
                    f"Plugin '{plugin_class.__name__}' already loaded, skipping duplicate."
                )
                return

        _register_languages_of(plugin_class)
        instance = None
        try:
            instance = plugin_class(self.main_window)
            instance.on_plugin_loaded()
            self._plugins.append(instance)

            # Merge plugin translations into the language system
            translations = instance.get_translations()
            if translations:
                language_wrapper.merge_translations(translations)

            status_registry.publish(self.status_scope + ":" + plugin_class.__name__,
                                    instance.plugin_name, "loaded",
                                    "Optional dependencies, models and backends are checked on use",
                                    scope=self.status_scope)
            logger.info(
                f"Loaded plugin: {instance.plugin_name} v{instance.plugin_version}"
                f" by {instance.plugin_author}"
            )
        except Exception as e:
            if instance is not None:
                if instance in self._plugins:
                    self._plugins.remove(instance)
                try:
                    instance.on_plugin_unloaded()
                except Exception:
                    logger.exception("Failed to clean up partially loaded plugin")
            status_registry.publish(self.status_scope + ":" + plugin_class.__name__,
                                    plugin_class.plugin_name, "failed", str(e) or type(e).__name__,
                                    scope=self.status_scope)
            logger.exception(f"Failed to instantiate plugin '{plugin_class.__name__}': {e}")

    def refresh_imports(self) -> None:
        """Forget only this manager's plugin modules before explicit reload (not other windows)."""
        roots = tuple(path.resolve() for path in self._plugin_dirs)
        for name, module in tuple(sys.modules.items()):   # entries are deleted below
            origin = getattr(module, "__file__", None)
            if not origin or not any(Path(origin).resolve().is_relative_to(root) for root in roots):
                continue
            cached = getattr(module, "__cached__", None)
            if cached and any(Path(cached).resolve().is_relative_to(root) for root in roots):
                try:
                    Path(cached).unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove plugin bytecode %s", cached, exc_info=True)
            del sys.modules[name]
        importlib.invalidate_caches()

    def unload_all(self) -> None:
        """Unload all plugins (called on app shutdown)."""
        for plugin in reversed(self._plugins):
            try:
                plugin.on_plugin_unloaded()
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_plugin_unloaded error: {e}")
        self._plugins.clear()
        status_registry.clear(self.status_scope)


def register_plugin_languages(plugin_dirs: list[Path] | None = None) -> None:
    """Import the plugins and register the languages they add, without instantiating them.

    For the start-up path, before the main window exists (see
    :func:`apply_saved_language`); nothing but ``register_languages`` runs.
    """
    if plugin_dirs is None:
        plugin_dirs = [_plugins_dir()]
    for plugin_class in _plugin_classes(plugin_dirs):
        _register_languages_of(plugin_class)


def apply_saved_language(language: str, plugin_dirs: list[Path] | None = None) -> None:
    """Make ``language`` the UI language, registering plugin languages first when needed.

    The main window builds its text in this language before any plugin is
    loaded, so a plugin language (Spanish) has to be registered here. A
    language no plugin provides any more leaves the current one in place.
    """
    if language not in language_wrapper.choose_language_dict:
        register_plugin_languages(plugin_dirs)
    language_wrapper.reset_language(language)
