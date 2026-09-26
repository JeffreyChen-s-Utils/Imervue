from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.system.app_paths import plugins_dir as _plugins_dir

logger = logging.getLogger("Imervue.plugin")


class PluginManager:
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
        self.main_window = main_window
        self._plugins: list[ImervuePlugin] = []
        self._plugin_dirs: list[Path] = []

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

        for plugin_class in _plugin_classes(plugin_dirs):
            self._instantiate(plugin_class)

    def _instantiate(self, plugin_class: type[ImervuePlugin]) -> None:
        """Instantiate ``plugin_class`` once, run ``on_plugin_loaded`` and merge its strings."""
        for existing in self._plugins:
            if type(existing).__name__ == plugin_class.__name__:
                logger.warning(
                    f"Plugin '{plugin_class.__name__}' already loaded, skipping duplicate."
                )
                return

        try:
            instance = plugin_class(self.main_window)
            self._plugins.append(instance)
            instance.on_plugin_loaded()

            # Merge plugin translations into the language system
            translations = instance.get_translations()
            if translations:
                language_wrapper.merge_translations(translations)

            logger.info(
                f"Loaded plugin: {instance.plugin_name} v{instance.plugin_version}"
                f" by {instance.plugin_author}"
            )
        except Exception as e:
            logger.exception(f"Failed to instantiate plugin '{plugin_class.__name__}': {e}")

    # ===========================
    # Hook Dispatch
    # ===========================

    def dispatch_build_menu_bar(self, plugin_menu) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_build_menu_bar(plugin_menu)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_build_menu_bar error: {e}")

    def dispatch_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_build_context_menu(menu, viewer)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_build_context_menu error: {e}")

    def dispatch_image_loaded(self, image_path: str, viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_image_loaded(image_path, viewer)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_image_loaded error: {e}")

    def dispatch_folder_opened(
        self, folder_path: str, image_paths: list[str], viewer: GPUImageView,
    ) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_folder_opened(folder_path, image_paths, viewer)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_folder_opened error: {e}")

    def dispatch_image_switched(self, image_path: str, viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_image_switched(image_path, viewer)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_image_switched error: {e}")

    def dispatch_image_deleted(self, deleted_paths: list[str], viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_image_deleted(deleted_paths, viewer)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_image_deleted error: {e}")

    def dispatch_key_press(self, key: int, modifiers: int, viewer: GPUImageView) -> bool:
        """Dispatch key press to plugins. Returns True if any plugin consumed the event."""
        for plugin in self._plugins:
            try:
                if plugin.on_key_press(key, modifiers, viewer):
                    return True
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_key_press error: {e}")
        return False

    def dispatch_app_closing(self, main_window: ImervueMainWindow) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_app_closing(main_window)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_app_closing error: {e}")

    def unload_all(self) -> None:
        """Unload all plugins (called on app shutdown)."""
        for plugin in reversed(self._plugins):
            try:
                plugin.on_plugin_unloaded()
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_plugin_unloaded error: {e}")
        self._plugins.clear()


def _plugin_candidates(plugin_dirs: list[Path]) -> Iterator[Path]:
    """Yield each plugin package directory and single-file plugin, in name order.

    Each existing directory is put on ``sys.path`` first, so plugins import
    their own modules as ``<plugin_name>.<module>``.
    """
    for plugin_dir in plugin_dirs:
        if not plugin_dir.is_dir():
            logger.info(f"Plugin directory does not exist, skipping: {plugin_dir}")
            continue

        # Add plugin dir to sys.path so imports work
        dir_str = str(plugin_dir)
        if dir_str not in sys.path:
            sys.path.insert(0, dir_str)

        yield from filter(_is_plugin_candidate, sorted(plugin_dir.iterdir()))


def _is_plugin_candidate(path: Path) -> bool:
    """A package directory with an ``__init__.py``, or a ``.py`` file other than ``__init__``."""
    if path.is_dir():
        return (path / "__init__.py").exists()
    return path.is_file() and path.suffix == ".py" and path.stem != "__init__"


def _import_plugin(candidate: Path) -> ModuleType | None:
    """Import a plugin package (cached by ``importlib``) or execute a single-file plugin."""
    if candidate.is_dir():
        module_name = candidate.name
        logger.info("Importing plugin package '%s' from %s", module_name, candidate)
        module = importlib.import_module(module_name)
        logger.info("Successfully imported '%s', registering...", module_name)
        return module
    module_name = candidate.stem
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if not (spec and spec.loader):
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _plugin_class_in(module: ModuleType, source: Path) -> type[ImervuePlugin] | None:
    """Return the module's ``plugin_class``, else its first ImervuePlugin subclass."""
    plugin_class = getattr(module, "plugin_class", None)

    if plugin_class is None:
        # Search for ImervuePlugin subclasses in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                    and issubclass(attr, ImervuePlugin)
                    and attr is not ImervuePlugin):
                plugin_class = attr
                break

    if plugin_class is None:
        logger.warning(f"No plugin class found in '{source}', skipping.")
        return None

    if not (isinstance(plugin_class, type) and issubclass(plugin_class, ImervuePlugin)):
        logger.warning(
            f"plugin_class in '{source}' is not a subclass of ImervuePlugin, skipping."
        )
        return None
    return plugin_class


def _plugin_classes(plugin_dirs: list[Path]) -> Iterator[type[ImervuePlugin]]:
    """Import every plugin under ``plugin_dirs`` and yield its plugin class.

    A plugin that fails to import is logged and skipped, so one broken plugin
    never stops the others from loading.
    """
    for candidate in _plugin_candidates(plugin_dirs):
        try:
            module = _import_plugin(candidate)
            plugin_class = None if module is None else _plugin_class_in(module, candidate)
        except Exception as e:  # plugin sandboxing: any import-time error
            logger.exception(f"Failed to load plugin '{candidate.name}': {e}")
            continue
        if plugin_class is not None:
            yield plugin_class
