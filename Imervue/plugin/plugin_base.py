from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from PySide6.QtWidgets import QMenu, QMenuBar
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class ImervuePlugin:
    """Base class for all Imervue plugins.

    Plugin developers should subclass this and override the hooks they need.
    Each hook method is called at a specific point in the application lifecycle.

    Required class attributes:
        plugin_name (str): Display name of the plugin.
        plugin_version (str): Version string (e.g. "1.0.0").
        plugin_description (str): Short description of what the plugin does.
        plugin_author (str): Author name or email.
    """

    plugin_name: str = "Unnamed Plugin"
    plugin_version: str = "0.0.1"
    plugin_description: str = ""
    plugin_author: str = ""

    def __init__(self, main_window: ImervueMainWindow):
        self.main_window: ImervueMainWindow = main_window
        self.viewer: GPUImageView = main_window.viewer

    # ===========================
    # Lifecycle Hooks
    # ===========================

    def on_plugin_loaded(self) -> None:
        """Called after the plugin is successfully loaded and registered.

        Use this for one-time initialization: setting up internal state,
        connecting to external services, etc.
        """
        pass

    def on_plugin_unloaded(self) -> None:
        """Called when the plugin is being unloaded or the application is closing.

        Use this to clean up resources: close files, disconnect signals, etc.
        """
        pass

    # ===========================
    # Menu Hooks
    # ===========================

    def on_build_menu_bar(self, plugin_menu: QMenu) -> None:
        """Called after the Plugin menu is built.

        Add your own submenus or actions into the shared Plugin menu.

        Example::

            my_menu = plugin_menu.addMenu("My Plugin")
            action = my_menu.addAction("Do Something")
            action.triggered.connect(self.do_something)
        """
        pass

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        """Called when the right-click context menu is being built.

        Add your own context menu items here. The ``viewer`` parameter gives
        you access to the current state (tile_grid_mode, deep_zoom, selected_tiles, etc.)

        Example::

            action = menu.addAction("My Action")
            action.triggered.connect(self.my_action)
        """
        pass

    # ===========================
    # Image Hooks
    # ===========================

    def on_image_loaded(self, image_path: str, viewer: GPUImageView) -> None:
        """Called after a single image is loaded in deep zoom mode.

        Args:
            image_path: Absolute path to the loaded image.
            viewer: The GPUImageView instance.
        """
        pass

    def on_folder_opened(self, folder_path: str, image_paths: list[str], viewer: GPUImageView) -> None:
        """Called after a folder is opened and images are listed.

        Args:
            folder_path: Absolute path to the opened folder.
            image_paths: List of image file paths found in the folder.
            viewer: The GPUImageView instance.
        """
        pass

    def on_image_switched(self, image_path: str, viewer: GPUImageView) -> None:
        """Called when the user switches to a different image (next/previous).

        Args:
            image_path: Absolute path to the new current image.
            viewer: The GPUImageView instance.
        """
        pass

    def on_image_deleted(self, deleted_paths: list[str], viewer: GPUImageView) -> None:
        """Called after image(s) are soft-deleted (added to undo stack).

        Args:
            deleted_paths: List of deleted image paths.
            viewer: The GPUImageView instance.
        """
        pass

    # ===========================
    # Input Hooks
    # ===========================

    def on_key_press(self, key: int, modifiers: int, viewer: GPUImageView) -> bool:
        """Called when a key is pressed in the viewer.

        Return True to consume the event (prevent default handling).
        Return False to let the default handler run.

        Args:
            key: Qt key code (e.g. Qt.Key.Key_F1).
            modifiers: Qt keyboard modifiers (e.g. Qt.KeyboardModifier.ControlModifier).
            viewer: The GPUImageView instance.
        """
        return False

    # ===========================
    # Internationalization Hooks
    # ===========================

    def get_translations(self) -> dict[str, dict[str, str]]:
        """Return translation strings for this plugin's UI elements.

        Override this to provide localized strings for your plugin.
        The returned dict maps language codes to key-value translation pairs.
        These are merged into the global language dictionaries so you can
        use ``language_wrapper.language_word_dict.get("your_key")`` in your
        plugin just like built-in code does.

        Built-in language codes: "English", "Traditional_Chinese", "Chinese",
        "Korean", "Japanese". Plugin-registered languages can also be used.

        Example::

            def get_translations(self) -> dict[str, dict[str, str]]:
                return {
                    "English": {
                        "my_plugin_action": "Do Something",
                    },
                    "Chinese": {
                        "my_plugin_action": "执行操作",
                    },
                    "Traditional_Chinese": {
                        "my_plugin_action": "執行操作",
                    },
                }
        """
        return {}

    # ===========================
    # Application Hooks
    # ===========================

    def on_app_closing(self, main_window: ImervueMainWindow) -> None:
        """Called when the application is about to close.

        Use this for final cleanup or saving state.
        """
        pass
