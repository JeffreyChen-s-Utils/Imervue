"""Hook dispatch for :class:`Imervue.plugin.plugin_manager.PluginManager`.

Each hook reaches the loaded plugins in load order; a plugin whose hook raises
is logged and the next plugin still runs.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMenu
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView
    from Imervue.plugin.plugin_base import ImervuePlugin

logger = logging.getLogger("Imervue.plugin")


class PluginDispatchMixin:
    """The ``dispatch_*`` hooks and the Desktop Pet hook wiring of the plugin manager."""

    main_window: ImervueMainWindow
    _plugins: list[ImervuePlugin]
    _pet_hook_connected: bool

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

    def dispatch_key_press(
        self, key: int, modifiers: Qt.KeyboardModifier, viewer: GPUImageView,
    ) -> bool:
        """Dispatch key press to plugins. Returns True if any plugin consumed the event."""
        for plugin in self._plugins:
            try:
                if plugin.on_key_press(key, modifiers, viewer):
                    return True
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_key_press error: {e}")
        return False

    def dispatch_pet_created(self, pet) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_pet_created(pet)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_pet_created error: {e}")

    def connect_pet_hooks(self) -> None:
        """Send ``on_pet_created`` for the pet that exists now and each one created later.

        Called after the plugins load and again after Reload Plugins; the
        connection to the Desktop Pet tab is made once. A window without the
        tab (or a test double) is left alone.
        """
        workspace = getattr(self.main_window, "pet_workspace", None)
        if workspace is None:
            return
        if not self._pet_hook_connected:
            workspace.pet_created.connect(self.dispatch_pet_created)
            self._pet_hook_connected = True
        pet = workspace.pet_window()
        if pet is not None:
            self.dispatch_pet_created(pet)

    def dispatch_app_closing(self, main_window: ImervueMainWindow) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_app_closing(main_window)
            except Exception as e:
                logger.exception(f"[{plugin.plugin_name}] on_app_closing error: {e}")
