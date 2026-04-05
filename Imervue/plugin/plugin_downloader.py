from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar,
    QMessageBox, QHeaderView,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.app_paths import plugins_dir as _plugins_dir

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.plugin.downloader")

REPO_API_URL = "https://api.github.com/repos/Jeffrey-Plugin-Repos/Imervue_Plugins/contents"
RAW_BASE_URL = "https://raw.githubusercontent.com/Jeffrey-Plugin-Repos/Imervue_Plugins/main"


def _get_plugin_dir() -> Path:
    return _plugins_dir()


def _github_get(url: str) -> list | dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


# ================================================================
# Worker: fetch available plugins list from GitHub
# ================================================================

class FetchPluginListWorker(QThread):
    result_ready = Signal(list)  # [(category, plugin_name, [file_info, ...])]
    error = Signal(str)

    def run(self):
        try:
            results = []
            root_items = _github_get(REPO_API_URL)

            categories = [
                item for item in root_items
                if item["type"] == "dir" and not item["name"].startswith(".")
            ]

            for cat in categories:
                cat_name = cat["name"]
                cat_items = _github_get(cat["url"])

                plugins = [
                    item for item in cat_items
                    if item["type"] == "dir"
                ]

                for plugin in plugins:
                    plugin_name = plugin["name"]
                    files = _github_get(plugin["url"])
                    file_infos = [
                        {
                            "name": f["name"],
                            "download_url": f["download_url"],
                            "path": f["path"],
                        }
                        for f in files if f["type"] == "file"
                    ]
                    results.append((cat_name, plugin_name, file_infos))

            self.result_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ================================================================
# Worker: download a single plugin
# ================================================================

class DownloadPluginWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    result_ready = Signal(str)       # plugin_name
    error = Signal(str)

    def __init__(self, plugin_name: str, file_infos: list[dict], parent=None):
        super().__init__(parent)
        self.plugin_name = plugin_name
        self.file_infos = file_infos

    def run(self):
        try:
            plugin_dir = _get_plugin_dir() / self.plugin_name
            plugin_dir.mkdir(parents=True, exist_ok=True)

            total = len(self.file_infos)
            for i, info in enumerate(self.file_infos):
                url = info["download_url"]
                dest = plugin_dir / info["name"]
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    dest.write_bytes(resp.read())
                self.progress.emit(i + 1, total)

            self.result_ready.emit(self.plugin_name)
        except Exception as e:
            self.error.emit(str(e))


# ================================================================
# Dialog
# ================================================================

class PluginDownloaderDialog(QDialog):
    def __init__(self, main_window: ImervueMainWindow, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self._plugin_data: list[tuple[str, str, list[dict]]] = []
        self._workers: list[QThread] = []

        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("plugin_dl_title", "Download Plugins"))
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)

        # --- Top buttons ---
        top_bar = QHBoxLayout()
        self.refresh_btn = QPushButton(lang.get("plugin_dl_refresh", "Refresh"))
        self.refresh_btn.clicked.connect(self._fetch_list)
        top_bar.addWidget(self.refresh_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # --- Tree ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            lang.get("plugin_dl_col_name", "Plugin"),
            lang.get("plugin_dl_col_status", "Status"),
        ])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.tree)

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # --- Status ---
        self.status_label = QLabel(lang.get("plugin_dl_status_ready", "Ready"))
        layout.addWidget(self.status_label)

        # --- Bottom buttons ---
        bottom_bar = QHBoxLayout()
        self.download_btn = QPushButton(lang.get("plugin_dl_download", "Download"))
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected)
        bottom_bar.addWidget(self.download_btn)

        self.delete_btn = QPushButton(lang.get("plugin_dl_delete", "Delete"))
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        bottom_bar.addWidget(self.delete_btn)

        bottom_bar.addStretch()

        self.close_btn = QPushButton(lang.get("plugin_dl_close", "Close"))
        self.close_btn.clicked.connect(self.close)
        bottom_bar.addWidget(self.close_btn)
        layout.addLayout(bottom_bar)

        # --- Signals ---
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        # Auto fetch on open
        self._fetch_list()

    # ========================
    # Cleanup
    # ========================

    def closeEvent(self, event):
        for w in self._workers:
            if w.isRunning():
                w.wait(5000)
        self._workers.clear()
        super().closeEvent(event)

    # ========================
    # Fetch plugin list
    # ========================

    def _fetch_list(self):
        lang = language_wrapper.language_word_dict
        self.refresh_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText(lang.get("plugin_dl_status_fetching", "Fetching plugin list..."))
        self.tree.clear()

        self._cleanup_finished_workers()
        worker = FetchPluginListWorker(self)
        worker.result_ready.connect(self._on_list_fetched)
        worker.error.connect(self._on_list_error)
        self._workers.append(worker)
        worker.start()

    def _on_list_fetched(self, results: list):
        lang = language_wrapper.language_word_dict
        self._plugin_data = results
        self.tree.clear()

        installed = self._get_installed_plugins()

        # Group by category
        categories: dict[str, list] = {}
        for cat, name, files in results:
            categories.setdefault(cat, []).append((name, files))

        for cat_name, plugins in categories.items():
            cat_item = QTreeWidgetItem(self.tree, [cat_name, ""])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            for plugin_name, files in plugins:
                is_installed = plugin_name in installed
                status = (
                    lang.get("plugin_dl_installed", "Installed")
                    if is_installed
                    else lang.get("plugin_dl_not_installed", "Not Installed")
                )
                child = QTreeWidgetItem(cat_item, [plugin_name, status])
                child.setData(0, Qt.ItemDataRole.UserRole, (plugin_name, files))

            cat_item.setExpanded(True)

        count = sum(len(v) for v in categories.values())
        self.status_label.setText(
            lang.get("plugin_dl_status_found", "Found {count} plugin(s)").format(count=count)
        )
        self.refresh_btn.setEnabled(True)

    def _on_list_error(self, error_msg: str):
        lang = language_wrapper.language_word_dict
        self.status_label.setText(
            lang.get("plugin_dl_status_error", "Error: {error}").format(error=error_msg)
        )
        self.refresh_btn.setEnabled(True)

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
    # Download
    # ========================

    def _download_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return

        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return

        plugin_name, file_infos = data
        lang = language_wrapper.language_word_dict

        self.download_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(file_infos))
        self.status_label.setText(
            lang.get("plugin_dl_status_downloading", "Downloading {name}...").format(name=plugin_name)
        )

        self._cleanup_finished_workers()
        worker = DownloadPluginWorker(plugin_name, file_infos, self)
        worker.progress.connect(self._on_download_progress)
        worker.result_ready.connect(self._on_download_finished)
        worker.error.connect(self._on_download_error)
        self._workers.append(worker)
        worker.start()

    def _on_download_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_download_finished(self, plugin_name: str):
        lang = language_wrapper.language_word_dict
        self.progress_bar.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(
            lang.get("plugin_dl_status_done", "Downloaded {name} successfully!").format(name=plugin_name)
        )

        # Refresh tree status
        self._refresh_installed_status()

        QMessageBox.information(
            self,
            lang.get("plugin_dl_title", "Download Plugins"),
            lang.get("plugin_dl_restart_hint", "Plugin '{name}' downloaded. Restart Imervue to activate it.").format(
                name=plugin_name
            ),
        )
        self.accept()

    def _on_download_error(self, error_msg: str):
        lang = language_wrapper.language_word_dict
        self.progress_bar.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self._on_selection_changed()
        self.status_label.setText(
            lang.get("plugin_dl_status_error", "Error: {error}").format(error=error_msg)
        )

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
            lang.get("plugin_dl_delete_confirm", "Delete plugin '{name}'?").format(name=plugin_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        import shutil
        plugin_path = _get_plugin_dir() / plugin_name
        if plugin_path.is_dir():
            shutil.rmtree(plugin_path)

        self.status_label.setText(
            lang.get("plugin_dl_status_deleted", "Deleted {name}.").format(name=plugin_name)
        )
        self._refresh_installed_status()

    # ========================
    # Helpers
    # ========================

    def _cleanup_finished_workers(self):
        self._workers = [w for w in self._workers if w.isRunning()]

    @staticmethod
    def _get_installed_plugins() -> set[str]:
        plugin_dir = _get_plugin_dir()
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
