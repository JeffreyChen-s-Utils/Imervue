from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu, QMenuBar
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

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
            # Default: <project_root>/plugins/
            project_root = Path(__file__).resolve().parent.parent.parent
            default_dir = project_root / "plugins"
            plugin_dirs = [default_dir]

        self._plugin_dirs = plugin_dirs

        for plugin_dir in plugin_dirs:
            if not plugin_dir.is_dir():
                logger.info(f"Plugin directory does not exist, skipping: {plugin_dir}")
                continue

            # Add plugin dir to sys.path so imports work
            dir_str = str(plugin_dir)
            if dir_str not in sys.path:
                sys.path.insert(0, dir_str)

            for candidate in sorted(plugin_dir.iterdir()):
                if candidate.is_dir() and (candidate / "__init__.py").exists():
                    self._load_plugin_package(candidate)
                elif candidate.is_file() and candidate.suffix == ".py" and candidate.stem != "__init__":
                    self._load_plugin_file(candidate)

    def _load_plugin_package(self, package_dir: Path) -> None:
        """Load a plugin from a package directory."""
        module_name = package_dir.name
        try:
            module = importlib.import_module(module_name)
            self._register_from_module(module, package_dir)
        except Exception as e:
            logger.error(f"Failed to load plugin package '{module_name}': {e}")

    def _load_plugin_file(self, file_path: Path) -> None:
        """Load a plugin from a single .py file."""
        module_name = file_path.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._register_from_module(module, file_path)
        except Exception as e:
            logger.error(f"Failed to load plugin file '{file_path.name}': {e}")

    def _register_from_module(self, module, source: Path) -> None:
        """Extract plugin_class from a module and instantiate it."""
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
            return

        if not (isinstance(plugin_class, type) and issubclass(plugin_class, ImervuePlugin)):
            logger.warning(
                f"plugin_class in '{source}' is not a subclass of ImervuePlugin, skipping."
            )
            return

        # Check for duplicates
        for existing in self._plugins:
            if type(existing).__name__ == plugin_class.__name__:
                logger.warning(f"Plugin '{plugin_class.__name__}' already loaded, skipping duplicate.")
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
            logger.error(f"Failed to instantiate plugin '{plugin_class.__name__}': {e}")

    # ===========================
    # Hook Dispatch
    # ===========================

    def dispatch_build_menu_bar(self, menu_bar: QMenuBar) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_build_menu_bar(menu_bar)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_build_menu_bar error: {e}")

    def dispatch_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_build_context_menu(menu, viewer)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_build_context_menu error: {e}")

    def dispatch_image_loaded(self, image_path: str, viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_image_loaded(image_path, viewer)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_image_loaded error: {e}")

    def dispatch_folder_opened(self, folder_path: str, image_paths: list[str], viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_folder_opened(folder_path, image_paths, viewer)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_folder_opened error: {e}")

    def dispatch_image_switched(self, image_path: str, viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_image_switched(image_path, viewer)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_image_switched error: {e}")

    def dispatch_image_deleted(self, deleted_paths: list[str], viewer: GPUImageView) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_image_deleted(deleted_paths, viewer)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_image_deleted error: {e}")

    def dispatch_key_press(self, key: int, modifiers: int, viewer: GPUImageView) -> bool:
        """Dispatch key press to plugins. Returns True if any plugin consumed the event."""
        for plugin in self._plugins:
            try:
                if plugin.on_key_press(key, modifiers, viewer):
                    return True
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_key_press error: {e}")
        return False

    def dispatch_app_closing(self, main_window: ImervueMainWindow) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_app_closing(main_window)
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_app_closing error: {e}")

    def unload_all(self) -> None:
        """Unload all plugins (called on app shutdown)."""
        for plugin in reversed(self._plugins):
            try:
                plugin.on_plugin_unloaded()
            except Exception as e:
                logger.error(f"[{plugin.plugin_name}] on_plugin_unloaded error: {e}")
        self._plugins.clear()
