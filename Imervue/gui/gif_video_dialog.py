"""
GIF/影片製作
Create GIF or MP4 video from selected images.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QFileDialog, QLineEdit, QProgressBar,
    QListWidget, QListWidgetItem, QGroupBox, QCheckBox,
)
from PIL import Image

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gif_video")


class _CreateWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(bool, str)  # success, message

    def __init__(self, paths, output_path, fmt, fps, width, height, loop):
        super().__init__()
        self._paths = paths
        self._output = output_path
        self._fmt = fmt
        self._fps = fps
        self._width = width
        self._height = height
        self._loop = loop

    def run(self):
        try:
            if self._fmt == "GIF":
                self._create_gif()
            else:
                self._create_video()
            self.finished.emit(True, self._output)
        except Exception as exc:
            logger.error(f"Create {self._fmt} failed: {exc}")
            self.finished.emit(False, str(exc))

    def _load_and_resize(self, path: str) -> Image.Image:
        if Path(path).suffix.lower() == ".svg":
            from Imervue.gpu_image_view.images.image_loader import _load_svg
            arr = _load_svg(path, thumbnail=False)
            img = Image.fromarray(arr)
        else:
            img = Image.open(path)

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        if self._width > 0 and self._height > 0:
            img = img.resize((self._width, self._height), Image.Resampling.LANCZOS)
        elif self._width > 0 or self._height > 0:
            img.thumbnail(
                (self._width or img.width, self._height or img.height),
                Image.Resampling.LANCZOS,
            )
        return img

    def _create_gif(self):
        frames = []
        total = len(self._paths)
        for i, path in enumerate(self._paths):
            img = self._load_and_resize(path)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            frames.append(img)
            self.progress.emit(i + 1, total)

        if not frames:
            return

        duration = int(1000 / max(self._fps, 1))
        loop_val = 0 if self._loop else 1

        frames[0].save(
            self._output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=loop_val,
            optimize=True,
        )

    def _create_video(self):
        import subprocess
        import sys
        import tempfile
        import shutil

        # Check ffmpeg
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.finished.emit(False, "ffmpeg not found in PATH")
            return

        total = len(self._paths)
        tmpdir = tempfile.mkdtemp(prefix="imervue_video_")

        try:
            # Write frames as numbered images
            for i, path in enumerate(self._paths):
                img = self._load_and_resize(path)
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                frame_path = Path(tmpdir) / f"frame_{i:06d}.png"
                img.save(str(frame_path), format="PNG")
                self.progress.emit(i + 1, total)

            # Use ffmpeg to combine
            pattern = str(Path(tmpdir) / "frame_%06d.png")
            cmd = [
                ffmpeg, "-y",
                "-framerate", str(self._fps),
                "-i", pattern,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                self._output,
            ]
            kw = {
                "capture_output": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": 300,
                "stdin": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, **kw)
            if result.returncode != 0:
                self.finished.emit(False, f"ffmpeg error: {result.stderr[:200]}")
                return
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class GifVideoDialog(QDialog):
    def __init__(self, main_gui: GPUImageView, paths: list[str]):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = list(paths)
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(self._lang.get("gif_video_title", "Create GIF / Video"))
        self.setMinimumSize(520, 520)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Image list (reorderable)
        layout.addWidget(QLabel(
            self._lang.get("gif_video_order", "Drag to reorder (top = first frame):")
        ))
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        for p in self._paths:
            item = QListWidgetItem(Path(p).name)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._list.addItem(item)
        layout.addWidget(self._list)

        # Move up/down buttons
        order_row = QHBoxLayout()
        up_btn = QPushButton(self._lang.get("gif_video_move_up", "Move Up"))
        up_btn.clicked.connect(self._move_up)
        down_btn = QPushButton(self._lang.get("gif_video_move_down", "Move Down"))
        down_btn.clicked.connect(self._move_down)
        order_row.addWidget(up_btn)
        order_row.addWidget(down_btn)
        order_row.addStretch()
        layout.addLayout(order_row)

        # Settings
        settings = QGroupBox(self._lang.get("gif_video_settings", "Settings"))
        slay = QVBoxLayout(settings)

        # Format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(self._lang.get("export_format", "Format:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["GIF", "MP4"])
        self._fmt_combo.currentTextChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self._fmt_combo)
        slay.addLayout(fmt_row)

        # FPS
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel(self._lang.get("gif_video_fps", "FPS:")))
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 60)
        self._fps_spin.setValue(5)
        fps_row.addWidget(self._fps_spin)
        fps_row.addStretch()
        slay.addLayout(fps_row)

        # Size
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self._lang.get("gif_video_width", "Width:")))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(0, 99999)
        self._width_spin.setValue(0)
        self._width_spin.setSpecialValueText(self._lang.get("gif_video_auto", "Auto"))
        size_row.addWidget(self._width_spin)
        size_row.addWidget(QLabel(self._lang.get("gif_video_height", "Height:")))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(0, 99999)
        self._height_spin.setValue(0)
        self._height_spin.setSpecialValueText(self._lang.get("gif_video_auto", "Auto"))
        size_row.addWidget(self._height_spin)
        slay.addLayout(size_row)

        # Loop (GIF only)
        self._loop_check = QCheckBox(self._lang.get("gif_video_loop", "Loop forever"))
        self._loop_check.setChecked(True)
        slay.addWidget(self._loop_check)

        layout.addWidget(settings)

        # Output path
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        if self._paths:
            default = Path(self._paths[0]).parent / "output.gif"
            self._path_edit.setText(str(default))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._create_btn = QPushButton(self._lang.get("gif_video_create", "Create"))
        self._create_btn.clicked.connect(self._do_create)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._create_btn)
        layout.addLayout(btn_row)

    def _on_format_changed(self, text):
        is_gif = text == "GIF"
        self._loop_check.setVisible(is_gif)
        # Update extension in path
        path = self._path_edit.text()
        if path:
            p = Path(path)
            ext = ".gif" if is_gif else ".mp4"
            self._path_edit.setText(str(p.with_suffix(ext)))

    def _move_up(self):
        row = self._list.currentRow()
        if row > 0:
            item = self._list.takeItem(row)
            self._list.insertItem(row - 1, item)
            self._list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._list.currentRow()
        if row < self._list.count() - 1:
            item = self._list.takeItem(row)
            self._list.insertItem(row + 1, item)
            self._list.setCurrentRow(row + 1)

    def _browse(self):
        fmt = self._fmt_combo.currentText()
        ext = ".gif" if fmt == "GIF" else ".mp4"
        path, _ = QFileDialog.getSaveFileName(
            self, self._lang.get("gif_video_save", "Save As"),
            self._path_edit.text(),
            f"{fmt} (*{ext})",
        )
        if path:
            self._path_edit.setText(path)

    def _get_ordered_paths(self) -> list[str]:
        paths = []
        for i in range(self._list.count()):
            paths.append(self._list.item(i).data(Qt.ItemDataRole.UserRole))
        return paths

    def _do_create(self):
        output = self._path_edit.text().strip()
        if not output:
            return

        paths = self._get_ordered_paths()
        if not paths:
            return

        self._create_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(paths))
        self._progress.setValue(0)

        self._worker = _CreateWorker(
            paths, output,
            self._fmt_combo.currentText(),
            self._fps_spin.value(),
            self._width_spin.value(),
            self._height_spin.value(),
            self._loop_check.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current, total):
        self._progress.setValue(current)
        self._status_label.setText(f"{current}/{total}")

    def _on_finished(self, success, message):
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)
        self._worker = None

        if success:
            msg = self._lang.get("gif_video_done", "Created: {path}").format(path=message)
            self._status_label.setText(msg)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(msg)
            self.accept()
        else:
            self._status_label.setText(f"Error: {message}")
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(f"Error: {message}")


def open_gif_video_dialog(main_gui: GPUImageView):
    paths = list(main_gui.selected_tiles)
    if not paths:
        return
    dlg = GifVideoDialog(main_gui, paths)
    dlg.exec()
