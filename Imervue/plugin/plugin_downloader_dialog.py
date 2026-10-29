"""The Download Plugins dialog: list the distribution repo, download, delete.

Installed-state handling (selection buttons, delete, status refresh) is in
:class:`PluginDownloaderInstalledMixin`; the workers are in
:mod:`plugin_downloader_workers`.
"""
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar,
    QMessageBox, QHeaderView,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.gui.background_jobs import job_registry
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.plugin.plugin_downloader_installed import PluginDownloaderInstalledMixin
from Imervue.plugin.plugin_downloader_workers import (
    DownloadPluginWorker,
    FetchPluginListWorker,
    _retry_download,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

# ================================================================
# Dialog
# ================================================================

class PluginDownloaderDialog(PluginDownloaderInstalledMixin, WorkerHostMixin, QDialog):
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

    def _stop_worker(self) -> bool:
        # Expose list-held threads to the shared nonblocking retirement contract.
        self._worker_attrs = tuple(f"_download_worker_{i}" for i in range(len(self._workers)))
        for attr, worker in zip(self._worker_attrs, self._workers, strict=True):
            setattr(self, attr, worker)
        self._workers.clear()
        return super()._stop_worker()

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
            lang.get("plugin_dl_status_downloading", "Downloading {name}...")
                .format(name=plugin_name)
        )

        self._cleanup_finished_workers()
        worker = DownloadPluginWorker(plugin_name, file_infos, self)
        job_registry().add(worker, self.windowTitle(),
                           partial(_retry_download,
                                   file_infos=tuple(dict(info) for info in file_infos)))
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
            lang.get("plugin_dl_status_done", "Downloaded {name} successfully!")
                .format(name=plugin_name)
        )

        # Refresh tree status
        self._refresh_installed_status()

        QMessageBox.information(
            self,
            lang.get("plugin_dl_title", "Download Plugins"),
            lang.get(
                "plugin_dl_restart_hint",
                "Plugin '{name}' downloaded. Restart Imervue to activate it.",
            ).format(name=plugin_name),
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
    # Helpers
    # ========================

    def _cleanup_finished_workers(self):
        self._workers = [w for w in self._workers if w.isRunning()]

