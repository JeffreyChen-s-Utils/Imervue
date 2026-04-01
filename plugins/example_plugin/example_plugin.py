"""
Example Plugin for Imervue
==========================

This is a reference plugin that demonstrates all available hooks.
Plugin developers can use this as a template.

To activate: place this folder in the ``plugins/`` directory.
To deactivate: remove or rename the folder.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu, QMenuBar
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class ExamplePlugin(ImervuePlugin):
    """Example plugin that logs events to the console and adds a menu item."""

    plugin_name = "Example Plugin"
    plugin_version = "1.0.0"
    plugin_description = "A reference plugin demonstrating all Imervue plugin hooks."
    plugin_author = "Imervue Team"

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__(main_window)
        self._image_count = 0

    # ===========================
    # Lifecycle
    # ===========================

    def on_plugin_loaded(self) -> None:
        print(f"[ExamplePlugin] Loaded! v{self.plugin_version}")

    def on_plugin_unloaded(self) -> None:
        print(f"[ExamplePlugin] Unloaded. Total images viewed: {self._image_count}")

    # ===========================
    # Menu
    # ===========================

    def on_build_menu_bar(self, menu_bar: QMenuBar) -> None:
        """Add an 'Example' menu to the menu bar."""
        example_menu = menu_bar.addMenu("Example Plugin")

        about_action = example_menu.addAction("About Example Plugin")
        about_action.triggered.connect(self._show_about)

        count_action = example_menu.addAction("Show Image Count")
        count_action.triggered.connect(self._show_count)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        """Add a custom item to the right-click context menu."""
        menu.addSeparator()
        action = menu.addAction("[Example] Print Current State")
        action.triggered.connect(lambda: self._print_state(viewer))

    # ===========================
    # Image Events
    # ===========================

    def on_image_loaded(self, image_path: str, viewer: GPUImageView) -> None:
        self._image_count += 1
        print(f"[ExamplePlugin] Image loaded: {Path(image_path).name} (#{self._image_count})")

    def on_folder_opened(self, folder_path: str, image_paths: list[str], viewer: GPUImageView) -> None:
        print(f"[ExamplePlugin] Folder opened: {folder_path} ({len(image_paths)} images)")

    def on_image_switched(self, image_path: str, viewer: GPUImageView) -> None:
        self._image_count += 1
        print(f"[ExamplePlugin] Switched to: {Path(image_path).name}")

    def on_image_deleted(self, deleted_paths: list[str], viewer: GPUImageView) -> None:
        names = [Path(p).name for p in deleted_paths]
        print(f"[ExamplePlugin] Deleted: {', '.join(names)}")

    # ===========================
    # Input
    # ===========================

    def on_key_press(self, key: int, modifiers: int, viewer: GPUImageView) -> bool:
        """Example: press F1 to show image count."""
        if key == Qt.Key.Key_F1:
            self._show_count()
            return True  # Consume the event
        return False

    # ===========================
    # Application
    # ===========================

    def on_app_closing(self, main_window: ImervueMainWindow) -> None:
        print(f"[ExamplePlugin] App closing. Total images viewed: {self._image_count}")

    # ===========================
    # Internal helpers
    # ===========================

    def _show_about(self):
        QMessageBox.information(
            self.main_window,
            "About Example Plugin",
            f"{self.plugin_name} v{self.plugin_version}\n"
            f"by {self.plugin_author}\n\n"
            f"{self.plugin_description}"
        )

    def _show_count(self):
        QMessageBox.information(
            self.main_window,
            "Image Count",
            f"Total images viewed this session: {self._image_count}"
        )

    def _print_state(self, viewer: GPUImageView):
        mode = "Tile Grid" if viewer.tile_grid_mode else "Deep Zoom" if viewer.deep_zoom else "Idle"
        total = len(viewer.model.images)
        selected = len(viewer.selected_tiles) if viewer.tile_selection_mode else 0
        print(f"[ExamplePlugin] State: mode={mode}, images={total}, selected={selected}")
