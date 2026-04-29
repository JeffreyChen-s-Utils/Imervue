"""
批次操作
Batch operations — rename, move/copy, rotate for selected tiles.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QRadioButton,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


# ===========================
# 批次重新命名
# ===========================

class BatchRenameDialog(QDialog):

    def __init__(self, main_gui: GPUImageView, paths: list[str]):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("batch_rename_title", "Batch Rename"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            lang.get("batch_rename_hint",
                      "Template: {name} = original name, {n} = sequence number, {ext} = extension")
        ))

        self._template = QLineEdit("{name}_{n}{ext}")
        layout.addWidget(self._template)

        row = QHBoxLayout()
        self._start_num = QLineEdit("1")
        self._start_num.setFixedWidth(60)
        row.addWidget(QLabel(lang.get("batch_rename_start", "Start number:")))
        row.addWidget(self._start_num)
        row.addStretch()
        layout.addLayout(row)

        # 預覽
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._preview_label)
        self._template.textChanged.connect(self._update_preview)
        self._start_num.textChanged.connect(self._update_preview)
        self._update_preview()

        btn_row = QHBoxLayout()
        ok = QPushButton(lang.get("batch_rename_apply", "Rename"))
        ok.clicked.connect(self._apply)
        cancel = QPushButton(lang.get("batch_rename_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _build_name(self, path: str, idx: int) -> str:
        p = Path(path)
        tmpl = self._template.text()
        return tmpl.format(name=p.stem, n=idx, ext=p.suffix)

    def _update_preview(self):
        try:
            start = int(self._start_num.text())
        except ValueError:
            start = 1
        lines = []
        for i, path in enumerate(self._paths[:5]):
            new_name = self._build_name(path, start + i)
            lines.append(f"{Path(path).name}  →  {new_name}")
        if len(self._paths) > 5:
            lines.append("...")
        self._preview_label.setText("\n".join(lines))

    def _apply(self):
        try:
            start = int(self._start_num.text())
        except ValueError:
            start = 1
        renamed, failed = self._rename_all(start)
        if renamed:
            self._apply_renames_to_model(renamed)
        self._show_batch_toast("Renamed", len(renamed), failed)
        if renamed:
            self._gui.selected_tiles.clear()
            self._gui.tile_selection_mode = False
            self._gui.clear_tile_grid()
            self._gui.load_tile_grid_async(self._gui.model.images)
        self.accept()

    def _rename_all(self, start: int) -> tuple[list[tuple[str, str]], int]:
        renamed: list[tuple[str, str]] = []
        failed = 0
        for i, old_path in enumerate(self._paths):
            p = Path(old_path)
            new_path = p.parent / self._build_name(old_path, start + i)
            try:
                if new_path != p and not new_path.exists():
                    p.rename(new_path)
                    renamed.append((old_path, str(new_path)))
                else:
                    failed += 1
            except OSError:
                failed += 1
        return renamed, failed

    def _apply_renames_to_model(self, renamed: list[tuple[str, str]]) -> None:
        images = self._gui.model.images
        for old, new in renamed:
            if old in images:
                images[images.index(old)] = new
            self._gui.tile_cache.pop(old, None)
            self._gui.tile_textures.pop(old, None)
            self._gui.selected_tiles.discard(old)

    def _show_batch_toast(self, op: str, succeeded: int, failed: int) -> None:
        if not hasattr(self._gui.main_window, "toast"):
            return
        msg = f"{op} {succeeded}/{succeeded + failed} file(s)"
        toast = self._gui.main_window.toast
        (toast.info if failed else toast.success)(msg)


# ===========================
# 批次移動/複製
# ===========================

class BatchMoveDialog(QDialog):

    def __init__(self, main_gui: GPUImageView, paths: list[str]):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("batch_move_title", "Move / Copy"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"{len(paths)} file(s) selected"))

        # 模式
        mode_grp = QGroupBox(lang.get("batch_move_mode", "Mode"))
        ml = QHBoxLayout(mode_grp)
        self._move_radio = QRadioButton(lang.get("batch_move_move", "Move"))
        self._copy_radio = QRadioButton(lang.get("batch_move_copy", "Copy"))
        self._move_radio.setChecked(True)
        ml.addWidget(self._move_radio)
        ml.addWidget(self._copy_radio)
        layout.addWidget(mode_grp)

        # 目標路徑
        dest_row = QHBoxLayout()
        self._dest = QLineEdit()
        browse = QPushButton("...")
        browse.setFixedWidth(40)
        browse.clicked.connect(self._browse)
        dest_row.addWidget(self._dest)
        dest_row.addWidget(browse)
        layout.addLayout(dest_row)

        btn_row = QHBoxLayout()
        ok = QPushButton(lang.get("batch_move_apply", "Apply"))
        ok.clicked.connect(self._apply)
        cancel = QPushButton(lang.get("batch_move_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._dest.setText(folder)

    def _apply(self):
        dest = self._dest.text().strip()
        if not dest or not Path(dest).is_dir():
            return
        is_move = self._move_radio.isChecked()
        count, failed = self._transfer_files(dest, is_move)
        if is_move and count:
            self._remove_moved_from_model()
        self._toast_transfer_result("Moved" if is_move else "Copied", count, failed)
        self.accept()

    def _transfer_files(self, dest: str, is_move: bool) -> tuple[int, int]:
        count = 0
        failed = 0
        for src in self._paths:
            target = Path(dest) / Path(src).name
            try:
                if is_move:
                    shutil.move(src, str(target))
                else:
                    shutil.copy2(src, str(target))
                count += 1
            except OSError:
                # shutil.Error already inherits from OSError on every supported
                # platform, so listing it explicitly is redundant.
                failed += 1
        return count, failed

    def _remove_moved_from_model(self) -> None:
        images = self._gui.model.images
        for src in self._paths:
            if src in images:
                images.remove(src)
            self._gui.tile_cache.pop(src, None)
            self._gui.tile_textures.pop(src, None)
        self._gui.selected_tiles.clear()
        self._gui.tile_selection_mode = False
        self._gui.clear_tile_grid()
        self._gui.load_tile_grid_async(images)

    def _toast_transfer_result(self, op: str, count: int, failed: int) -> None:
        if not hasattr(self._gui.main_window, "toast"):
            return
        msg = f"{op} {count}/{count + failed} file(s)"
        toast = self._gui.main_window.toast
        (toast.info if failed else toast.success)(msg)


# ===========================
# 批次旋轉
# ===========================

def batch_rotate(main_gui: GPUImageView, paths: list[str], degrees: int):
    """旋轉選取的圖片並儲存"""
    count = 0
    failed = 0
    for path in paths:
        try:
            img = Image.open(path)
            img = img.rotate(-degrees, expand=True)
            img.save(path)
            count += 1
            # 清除快取
            main_gui.tile_cache.pop(path, None)
            main_gui.tile_textures.pop(path, None)
        except Exception:
            failed += 1

    if count:
        main_gui.selected_tiles.clear()
        main_gui.tile_selection_mode = False
        main_gui.clear_tile_grid()
        main_gui.load_tile_grid_async(main_gui.model.images)

    if hasattr(main_gui.main_window, "toast"):
        msg = f"Rotated {count}/{count + failed} file(s)"
        if failed:
            main_gui.main_window.toast.info(msg)
        else:
            main_gui.main_window.toast.success(msg)


# ===========================
# 入口
# ===========================

def open_batch_rename(main_gui: GPUImageView):
    paths = list(main_gui.selected_tiles)
    if not paths:
        return
    dlg = BatchRenameDialog(main_gui, paths)
    dlg.exec()


def open_batch_move(main_gui: GPUImageView):
    paths = list(main_gui.selected_tiles)
    if not paths:
        return
    dlg = BatchMoveDialog(main_gui, paths)
    dlg.exec()
