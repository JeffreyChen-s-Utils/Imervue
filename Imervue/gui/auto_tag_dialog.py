"""
Auto-tagging dialog — run the heuristic / CLIP classifier on selected or all images.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QRadioButton, QButtonGroup, QPlainTextEdit,
)

from Imervue.library.auto_tag import auto_tag_batch
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.auto_tag")


class _AutoTagWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(int)
    error = Signal(str)

    def __init__(self, paths: list[str]):
        super().__init__()
        self._paths = paths

    def run(self) -> None:
        try:
            auto_tag_batch(
                self._paths,
                progress_cb=lambda c, t, p: self.progress.emit(c, t, p),
            )
        except Exception as exc:  # noqa: BLE001 - worker must always report
            # auto_tag_batch writes to SQLite, which can raise (e.g. database
            # locked while a scan runs); without this the progress bar hung
            # forever and the thread was never quit.
            logger.exception("Auto-tag failed: %s", exc)
            self.error.emit(str(exc))
            return
        self.done.emit(len(self._paths))


class AutoTagDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._thread: QThread | None = None
        self._worker: _AutoTagWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("auto_tag_title", "Auto-Tag Images"))
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("auto_tag_explain",
                     "Applies heuristic tags under 'auto/...' (photo/document/"
                     "screenshot/landscape/portrait etc.). Uses CLIP ONNX if installed.")
        ))

        self._scope_group = QButtonGroup(self)
        self._sel_radio = QRadioButton(lang.get("auto_tag_selected", "Selected"))
        self._all_radio = QRadioButton(lang.get("auto_tag_all", "Whole folder"))
        self._sel_radio.setChecked(True)
        self._scope_group.addButton(self._sel_radio)
        self._scope_group.addButton(self._all_radio)
        row = QHBoxLayout()
        row.addWidget(self._sel_radio)
        row.addWidget(self._all_radio)
        row.addStretch()
        layout.addLayout(row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton(lang.get("auto_tag_run", "Run"))
        self._run_btn.clicked.connect(self._run)
        close_btn = QPushButton(lang.get("common_close", "Close"))
        # close() (not accept()) so closeEvent joins the tagging thread first —
        # accept() delivers no closeEvent and would drop a live thread.
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _collect_paths(self) -> list[str]:
        viewer = self._ui.viewer
        if self._sel_radio.isChecked() and viewer.selected_tiles:
            return sorted(viewer.selected_tiles)
        return list(viewer.model.images)

    def _run(self) -> None:
        # Guard against a second Run while one is in flight — a double-click
        # would orphan the first thread and fire _on_done twice.
        if self._thread is not None and self._thread.isRunning():
            return
        paths = self._collect_paths()
        if not paths:
            return
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(paths))
        self._progress.setValue(0)
        self._worker = _AutoTagWorker(paths)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _teardown_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None

    def _on_progress(self, current: int, total: int, path: str) -> None:
        self._progress.setValue(current)
        self._log.appendPlainText(f"[{current}/{total}] {path}")

    def _on_done(self, total: int) -> None:
        self._progress.setVisible(False)
        self._teardown_thread()
        self._run_btn.setEnabled(True)
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                language_wrapper.language_word_dict.get(
                    "auto_tag_done", "Tagged {n} images"
                ).format(n=total)
            )

    def _on_error(self, message: str) -> None:
        self._progress.setVisible(False)
        self._teardown_thread()
        self._run_btn.setEnabled(True)
        self._log.appendPlainText(f"Error: {message}")
        if hasattr(self._ui, "toast"):
            self._ui.toast.error(
                language_wrapper.language_word_dict.get(
                    "auto_tag_failed", "Auto-tag failed: {msg}"
                ).format(msg=message)
            )

    def reject(self):  # noqa: N802 - Qt override
        # Esc / Cancel calls reject(), which delivers no closeEvent; tear the
        # tagging thread down here too so it is never dropped while running.
        self._teardown_thread()
        super().reject()

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        # Don't let the dialog be torn down with a live worker thread
        # ("QThread: Destroyed while running").
        self._teardown_thread()
        super().closeEvent(event)


def open_auto_tag(ui: ImervueMainWindow) -> None:
    AutoTagDialog(ui).exec()
