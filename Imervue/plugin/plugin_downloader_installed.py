"""Installed-plugin state for the Download Plugins dialog.

Which plugins are installed, the download/delete button state for the selected
row, deleting a plugin and refreshing the status column. ``_get_plugin_dir`` is
read from :mod:`plugin_downloader` at call time.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper


class PluginDownloaderInstalledMixin:
    """Selection, delete and installed-status behaviour of ``PluginDownloaderDialog``."""

    # ========================
    # Selection
    # ========================

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.download_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            self.download_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        plugin_name, _ = data
        installed = self._get_installed_plugins()
        is_installed = plugin_name in installed

        self.download_btn.setEnabled(True)
        self.delete_btn.setEnabled(is_installed)

        lang = language_wrapper.language_word_dict
        if is_installed:
            self.download_btn.setText(lang.get("plugin_dl_reinstall", "Reinstall"))
        else:
            self.download_btn.setText(lang.get("plugin_dl_download", "Download"))

    # ========================
    # Delete
    # ========================

    def _delete_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return

        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return

        plugin_name, _ = data
        lang = language_wrapper.language_word_dict

        reply = QMessageBox.question(
            self,
            lang.get("plugin_dl_delete_confirm_title", "Delete Plugin"),
            lang.get("plugin_dl_delete_confirm", "Delete plugin '{name}'?")
                .format(name=plugin_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        import shutil
        from Imervue.plugin import plugin_downloader as downloader
        plugin_path = downloader._get_plugin_dir() / plugin_name
        if plugin_path.is_dir():
            shutil.rmtree(plugin_path)

        self.status_label.setText(
            lang.get("plugin_dl_status_deleted", "Deleted {name}.").format(name=plugin_name)
        )
        self._refresh_installed_status()

    # ========================
    # Helpers
    # ========================

    @staticmethod
    def _get_installed_plugins() -> set[str]:
        from Imervue.plugin import plugin_downloader as downloader
        plugin_dir = downloader._get_plugin_dir()
        if not plugin_dir.is_dir():
            return set()
        return {
            p.name for p in plugin_dir.iterdir()
            if p.is_dir() and (p / "__init__.py").exists()
        }

    def _refresh_installed_status(self):
        lang = language_wrapper.language_word_dict
        installed = self._get_installed_plugins()

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    plugin_name, _ = data
                    is_installed = plugin_name in installed
                    child.setText(1,
                        lang.get("plugin_dl_installed", "Installed")
                        if is_installed
                        else lang.get("plugin_dl_not_installed", "Not Installed")
                    )

        self._on_selection_changed()

