"""
Auto-tagging dialog — run the heuristic / CLIP classifier on selected or all images.
"""
from __future__ import annotations

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


class _AutoTagWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(int)

    def __init__(self, paths: list[str]):
        super().__init__()
        self._paths = paths

    def run(self) -> None:
        auto_tag_batch(self._paths, progress_cb=lambda c, t, p: self.progress.emit(c, t, p))
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
        run_btn = QPushButton(lang.get("auto_tag_run", "Run"))
        run_btn.clicked.connect(self._run)
        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(run_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _collect_paths(self) -> list[str]:
        viewer = self._ui.viewer
        if self._sel_radio.isChecked() and viewer.selected_tiles:
            return sorted(viewer.selected_tiles)
        return list(viewer.model.images)

    def _run(self) -> None:
        paths = self._collect_paths()
        if not paths:
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, len(paths))
        self._progress.setValue(0)
        self._worker = _AutoTagWorker(paths)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._thread.start()

    def _on_progress(self, current: int, total: int, path: str) -> None:
        self._progress.setValue(current)
        self._log.appendPlainText(f"[{current}/{total}] {path}")

    def _on_done(self, total: int) -> None:
        self._progress.setVisible(False)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                language_wrapper.language_word_dict.get(
                    "auto_tag_done", "Tagged {n} images"
                ).format(n=total)
            )


def open_auto_tag(ui: ImervueMainWindow) -> None:
    AutoTagDialog(ui).exec()
