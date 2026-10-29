"""
Install Dependencies dialog: lists the missing packages and installs them.

The dialog searches for an interpreter, downloads a portable Python when none
is found on Windows, runs the install worker, imports the new packages and then
calls the caller's success callback. Closing it retires running workers without
blocking. :mod:`Imervue.plugin.pip_installer` re-exports the class.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.pip_embed_python import _DownloadPythonWorker
from Imervue.plugin.pip_install_workers import _FindPythonWorker, _ImportWorker, _InstallWorker
from Imervue.plugin.status import status_registry
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.plugin.worker_retirement import retire_workers
from Imervue.system.app_paths import is_frozen as _is_frozen

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger("Imervue.plugin.pip_installer")


# ===========================
# 安裝對話框
# ===========================

class InstallDependenciesDialog(WorkerHostMixin, QDialog):
    """顯示缺少套件並自動安裝；關閉時非阻塞保留執行中的工作。"""

    _worker_attrs = ("_worker", "_dl_worker", "_find_worker", "_import_worker")

    def __init__(
        self,
        parent: QWidget,
        missing: list[tuple[str, str]],
        on_success=None,
    ):
        super().__init__(parent)
        self._missing = missing
        self._status_key = "dependencies:" + ",".join(sorted(imp for imp, _pip in missing))
        self._publish_status("missing", ", ".join(pip for _imp, pip in missing))
        self._on_success = on_success
        self._worker = None
        self._dl_worker = None
        self._find_worker = None
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(
            lang.get("pip_install_title", "Install Dependencies")
        )
        self.setMinimumSize(520, 360)
        self._build_ui()

    def _publish_status(self, state: str, reason: str = "") -> None:
        status_registry.publish(self._status_key, self.windowTitle() or "Dependencies",
                                state, reason)

    def done(self, result: int) -> None:
        if result == QDialog.DialogCode.Rejected:
            self._publish_status("cancelling")
        super().done(result)
        if result == QDialog.DialogCode.Rejected and not getattr(self, "_worker_retiring", False):
            self._publish_status("cancelled")

    def _worker_retired(self) -> None:
        if getattr(self, "_worker_close_result", None) == QDialog.DialogCode.Rejected:
            self._publish_status("cancelled")
        super()._worker_retired()

    def _track_finished(self, worker: QThread, attr: str) -> None:
        worker.finished.connect(lambda: self._release_worker(worker, attr))

    def _release_worker(self, worker: QThread, attr: str) -> None:
        if getattr(self, attr, None) is not worker:
            return
        setattr(self, attr, None)
        retire_workers(self, [worker], lambda: None, cancel=False)

    def _build_ui(self):
        lang = language_wrapper.language_word_dict
        layout = QVBoxLayout(self)

        pip_names = [pip for _, pip in self._missing]
        desc = lang.get(
            "pip_install_desc",
            "The following packages are required but not installed:\n\n"
            "{packages}\n\n"
            "Click Install to download and install them automatically.",
        ).format(packages="\n".join(f"  - {n}" for n in pip_names))
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setVisible(False)
        self._log.setMaximumHeight(180)
        layout.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton(lang.get("export_cancel", "Cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        self._install_btn = QPushButton(
            lang.get("pip_install_btn", "Install")
        )
        self._install_btn.clicked.connect(self._do_install)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._install_btn)
        layout.addLayout(btn_row)

    # ----- 安裝流程 -----

    def _do_install(self):
        """按下安裝：先在背景搜尋 Python（不阻塞 UI）"""
        lang = language_wrapper.language_word_dict
        self._publish_status("checking")
        self._install_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.setVisible(True)
        self._log.append(lang.get(
            "pip_searching_python", "Searching for Python interpreter..."
        ))

        self._find_worker = _FindPythonWorker()
        self._find_worker.result_ready.connect(self._on_python_found)
        self._track_finished(self._find_worker, "_find_worker")
        self._find_worker.start()

    def _on_python_found(self, python: str | None):

        if python is not None:
            self._start_package_install(python)
            return

        # 找不到 Python → 嘗試自動下載 (僅 Windows)
        if sys.platform == "win32":
            self._start_python_download()
        else:
            self._progress.setVisible(False)
            self._install_btn.setEnabled(True)
            self._show_no_python_error()

    def _show_no_python_error(self):
        self._publish_status("failed", "No usable Python interpreter")
        lang = language_wrapper.language_word_dict
        self._log.setVisible(True)
        self._log.append(lang.get(
            "pip_no_python",
            "Cannot find a Python interpreter with pip.\n\n"
            "Please install Python from https://www.python.org/downloads/\n"
            "and make sure to check 'Add Python to PATH' during installation.",
        ))
        self._status.setText(lang.get(
            "pip_no_python_short",
            "Python not found. Please install Python first.",
        ))

    def _start_python_download(self):
        self._publish_status("downloading", "Portable Python")
        lang = language_wrapper.language_word_dict
        self._log.append(lang.get(
            "pip_downloading_python",
            "No Python found. Downloading portable Python automatically...",
        ))

        self._dl_worker = _DownloadPythonWorker()
        self._dl_worker.log.connect(self._on_log)
        self._dl_worker.result_ready.connect(self._on_python_downloaded)
        self._track_finished(self._dl_worker, "_dl_worker")
        self._dl_worker.start()

    def _on_python_downloaded(self, success: bool, result: str):
        if success:
            self._log.append(f"Portable Python ready: {result}")
            self._start_package_install(result)
        else:
            self._progress.setVisible(False)
            self._install_btn.setEnabled(True)
            self._log.append(f"\nFailed to download Python: {result}")
            self._show_no_python_error()
            self._publish_status("failed", result)

    def _start_package_install(self, python: str):
        self._publish_status("running", ", ".join(pip for _imp, pip in self._missing))
        self._log.append(f"Using Python: {python}")
        if _is_frozen():
            self._log.append("(Frozen/packaged environment detected)")

        pip_names = [pip for _, pip in self._missing]
        self._worker = _InstallWorker(pip_names, python)
        self._worker.log.connect(self._on_log)
        self._worker.result_ready.connect(self._on_finished)
        self._track_finished(self._worker, "_worker")
        self._worker.start()

    def _on_log(self, text: str):
        self._log.append(text)
        self._status.setText(text.split("\n", maxsplit=1)[0][:80])
        self._publish_status("running", text[:1000])

    def _on_finished(self, success: bool, message: str):

        if success:
            lang = language_wrapper.language_word_dict
            self._status.setText(
                lang.get("pip_install_done", "Installation complete!")
            )
            self._log.append(f"\n{message}")

            if _is_frozen():
                # 凍結環境：不在背景執行緒 import（native DLL 會 segfault）。
                # 套件的 on_ready callback 會在主執行緒完成 import。
                self._on_import_done()
            else:
                # 開發環境：在背景執行緒 import 剛安裝的套件（避免阻塞 UI）
                names = [imp for imp, _ in self._missing]
                self._import_worker = _ImportWorker(names)
                self._import_worker.result_ready.connect(self._on_import_done)
                self._import_worker.error.connect(self._on_import_failed)
                self._track_finished(self._import_worker, "_import_worker")
                self._import_worker.start()
        else:
            self._progress.setVisible(False)
            self._install_btn.setEnabled(True)
            self._publish_status("failed", message)
            self._status.setText(f"Error: {message[:100]}")
            self._log.append(f"\nError: {message}")

    def _on_import_failed(self, reason: str) -> None:
        self._publish_status("failed", reason)
        self._progress.setVisible(False)
        self._install_btn.setEnabled(True)
        self._status.setText(reason)
        self._log.append(reason)

    def _on_import_done(self):
        self._publish_status("available")
        self._progress.setVisible(False)
        self._install_btn.setEnabled(True)

        if self._on_success:
            try:
                self._on_success()
            except Exception as exc:
                logger.exception("Dependency-ready callback failed")
                self._on_import_failed(str(exc) or type(exc).__name__)
                return
        self.accept()
