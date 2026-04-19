"""
Dual-pane file manager dialog — Total Commander style.

Two QTreeView panels over QFileSystemModel with buttons to move or copy the
selection between panes. Aimed at power users sorting large photo archives
across folders without leaving Imervue.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QDir
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeView,
    QLineEdit, QFileDialog, QFileSystemModel, QMessageBox, QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


_SETTING_LEFT = "dual_pane_left_path"
_SETTING_RIGHT = "dual_pane_right_path"


class _Pane(QWidget):
    def __init__(self, setting_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._setting_key = setting_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.returnPressed.connect(self._apply_edited_path)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._model = QFileSystemModel(self)
        self._model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree.setSortingEnabled(True)
        self._tree.setColumnWidth(0, 240)
        layout.addWidget(self._tree, stretch=1)

        initial = user_setting_dict.get(setting_key) or str(Path.home())
        self.set_path(initial)

    def path(self) -> str:
        idx = self._tree.rootIndex()
        return self._model.filePath(idx) or self._path_edit.text()

    def set_path(self, path: str) -> None:
        if not Path(path).is_dir():
            return
        self._model.setRootPath(path)
        self._tree.setRootIndex(self._model.index(path))
        self._path_edit.setText(path)
        user_setting_dict[self._setting_key] = path
        schedule_save()

    def selected_paths(self) -> list[str]:
        return [
            self._model.filePath(i)
            for i in self._tree.selectionModel().selectedRows()
        ]

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "", self.path())
        if chosen:
            self.set_path(chosen)

    def _apply_edited_path(self) -> None:
        self.set_path(self._path_edit.text().strip())

    def refresh(self) -> None:
        self._model.setRootPath(self._model.rootPath())


class DualPaneDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("dual_pane_title", "Dual-Pane File Manager"))
        self.resize(1100, 640)

        layout = QVBoxLayout(self)
        panes_row = QHBoxLayout()
        self._left = _Pane(_SETTING_LEFT)
        self._right = _Pane(_SETTING_RIGHT)
        panes_row.addWidget(self._left, stretch=1)
        panes_row.addWidget(self._right, stretch=1)
        layout.addLayout(panes_row)

        btn_row = QHBoxLayout()
        copy_l2r = QPushButton(lang.get("dual_pane_copy_right", "Copy →"))
        copy_l2r.clicked.connect(
            lambda: self._transfer(src=self._left, dst=self._right, move=False))
        move_l2r = QPushButton(lang.get("dual_pane_move_right", "Move →"))
        move_l2r.clicked.connect(
            lambda: self._transfer(src=self._left, dst=self._right, move=True))
        move_r2l = QPushButton(lang.get("dual_pane_move_left", "← Move"))
        move_r2l.clicked.connect(
            lambda: self._transfer(src=self._right, dst=self._left, move=True))
        copy_r2l = QPushButton(lang.get("dual_pane_copy_left", "← Copy"))
        copy_r2l.clicked.connect(
            lambda: self._transfer(src=self._right, dst=self._left, move=False))
        open_btn = QPushButton(lang.get("dual_pane_open_in_viewer", "Open in viewer"))
        open_btn.clicked.connect(self._open_in_viewer)
        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        for b in (copy_l2r, move_l2r, move_r2l, copy_r2l, open_btn, close_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _transfer(self, *, src: _Pane, dst: _Pane, move: bool) -> None:
        paths = src.selected_paths()
        if not paths:
            return
        dest_dir = Path(dst.path())
        if not dest_dir.is_dir():
            QMessageBox.warning(self, "", "Destination is not a directory")
            return
        ok = failed = 0
        for p in paths:
            target = dest_dir / Path(p).name
            try:
                if move:
                    shutil.move(p, str(target))
                elif Path(p).is_dir():
                    shutil.copytree(p, str(target))
                else:
                    shutil.copy2(p, str(target))
                ok += 1
            except OSError:
                failed += 1
        self._left.refresh()
        self._right.refresh()
        if hasattr(self._ui, "toast"):
            lang = language_wrapper.language_word_dict
            key = "dual_pane_moved" if move else "dual_pane_copied"
            fallback = "Moved {ok} (failed {f})" if move else "Copied {ok} (failed {f})"
            self._ui.toast.info(lang.get(key, fallback).format(ok=ok, f=failed))

    def _open_in_viewer(self) -> None:
        sel = self._left.selected_paths() or self._right.selected_paths()
        if not sel:
            return
        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self._ui.viewer, path=sel[0])


def open_dual_pane(ui: ImervueMainWindow) -> None:
    DualPaneDialog(ui).exec()
