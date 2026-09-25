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
    QSpinBox, QPushButton, QProgressBar,
    QListWidget, QListWidgetItem, QGroupBox, QCheckBox,
)
from PIL import Image

from Imervue.system.qt_timers import call_later
from Imervue.gui.dialog_rows import (
    action_button_row, may_replace, path_browse_row, save_path_into,
)
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.gpu_image_view.actions.select import selected_in_view_order
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.free_names import free_names

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gif_video")


class _CreateWorker(QThread):
    progress = Signal(int, int)
    result_ready = Signal(bool, str)  # success, message

    def __init__(self, paths, output_path, fmt, fps, width, height, loop):
        super().__init__()
        self._paths = paths
        self._output = output_path
        self._fmt = fmt
        self._fps = fps
        self._width = width
        self._height = height
        self._loop = loop
        self._abort = False

    def abort(self) -> None:
        """Ask the encode loop to stop before the next frame (Cancel / close)."""
        self._abort = True

    def run(self):
        try:
            if self._fmt == "GIF":
                self._create_gif()
            else:
                self._create_video()
        except Exception as exc:
            logger.exception(f"Create {self._fmt} failed: {exc}")
            self.result_ready.emit(False, str(exc))
            return
        # Single terminal emit: the create helpers raise on failure (so a
        # missing ffmpeg or encode error can't be masked by a later success
        # emit) and simply return early when aborted.
        if self._abort:
            self.result_ready.emit(False, "cancelled")
        else:
            self.result_ready.emit(True, self._output)

    def _load_and_resize(self, path: str) -> Image.Image:
        # The viewer's decode — upright, sRGB, SVG rasterised, RAW / HEIC
        # developed. Image.open left a portrait phone photo on its side.
        from Imervue.gpu_image_view.images.image_loader import decode_image
        img = decode_image(path)

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
            if self._abort:
                return
            img = self._load_and_resize(path)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            frames.append(img)
            self.progress.emit(i + 1, total)

        if not frames:
            return

        # Loop count 0 is forever. Without a loop count the GIF plays once; a
        # count of 1 means one repeat, which browsers play twice.
        looping = {"loop": 0} if self._loop else {}
        frames[0].save(
            self._output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / max(self._fps, 1)),
            optimize=True,
            **looping,
        )

    def _create_video(self):
        import subprocess
        import sys
        import tempfile
        import shutil

        # Check ffmpeg
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found in PATH")

        total = len(self._paths)
        tmpdir = tempfile.mkdtemp(prefix="imervue_video_")

        try:
            # Write frames as numbered images
            for i, path in enumerate(self._paths):
                if self._abort:
                    return
                img = self._load_and_resize(path)
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                frame_path = Path(tmpdir) / f"frame_{i:06d}.png"
                img.save(str(frame_path), format="PNG")
                self.progress.emit(i + 1, total)

            if self._abort:
                return
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
            result = subprocess.run(cmd, check=False, **kw)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg error: {result.stderr[:200]}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class GifVideoDialog(WorkerHostMixin, QDialog):
    def __init__(self, main_gui: GPUImageView, paths: list[str]):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = list(paths)
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        # The suggested output path while it is still the suggestion, and the
        # path last picked through Browse… (its Save dialog asked about replacing).
        self._auto_output = ""
        self._browsed_path: str | None = None

        self.setWindowTitle(self._lang.get("gif_video_title", "Create GIF / Video"))
        self.setMinimumSize(520, 520)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Image list (reorderable)
        layout.addWidget(QLabel(
            self._lang.get("gif_video_order", "Drag to reorder (top = first frame):")
        ))
        layout.addWidget(self._build_frame_list())
        layout.addLayout(self._build_order_row())
        layout.addWidget(self._build_settings_group())

        # Output path
        path_row, self._path_edit, _browse = path_browse_row(
            self._browse, browse_text=self._lang.get("export_browse", "Browse..."))
        if self._paths:
            self._auto_output = self._suggested_output(".gif")
            self._path_edit.setText(self._auto_output)
        layout.addLayout(path_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self._on_cancel)
        self._create_btn = QPushButton(self._lang.get("gif_video_create", "Create"))
        self._create_btn.clicked.connect(self._do_create)
        layout.addLayout(action_button_row(cancel_btn, self._create_btn))

    def _build_frame_list(self) -> QListWidget:
        """Drag-reorderable frame list; each item carries its path as user data."""
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        for p in self._paths:
            item = QListWidgetItem(Path(p).name)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._list.addItem(item)
        return self._list

    def _build_order_row(self) -> QHBoxLayout:
        """Move Up / Move Down for the selected frame."""
        order_row = QHBoxLayout()
        up_btn = QPushButton(self._lang.get("gif_video_move_up", "Move Up"))
        up_btn.clicked.connect(self._move_up)
        down_btn = QPushButton(self._lang.get("gif_video_move_down", "Move Down"))
        down_btn.clicked.connect(self._move_down)
        order_row.addWidget(up_btn)
        order_row.addWidget(down_btn)
        order_row.addStretch()
        return order_row

    def _auto_size_spin(self) -> QSpinBox:
        """0–99999 px where 0 reads "Auto" (keep the source size)."""
        spin = QSpinBox()
        spin.setRange(0, 99999)
        spin.setValue(0)
        spin.setSpecialValueText(self._lang.get("gif_video_auto", "Auto"))
        return spin

    def _build_settings_group(self) -> QGroupBox:
        """Format, FPS, output size and the GIF-only loop box."""
        settings = QGroupBox(self._lang.get("gif_video_settings", "Settings"))
        slay = QVBoxLayout(settings)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(self._lang.get("export_format", "Format:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["GIF", "MP4"])
        self._fmt_combo.currentTextChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self._fmt_combo)
        slay.addLayout(fmt_row)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel(self._lang.get("gif_video_fps", "FPS:")))
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 60)
        self._fps_spin.setValue(5)
        fps_row.addWidget(self._fps_spin)
        fps_row.addStretch()
        slay.addLayout(fps_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self._lang.get("gif_video_width", "Width:")))
        self._width_spin = self._auto_size_spin()
        size_row.addWidget(self._width_spin)
        size_row.addWidget(QLabel(self._lang.get("gif_video_height", "Height:")))
        self._height_spin = self._auto_size_spin()
        size_row.addWidget(self._height_spin)
        slay.addLayout(size_row)

        # Loop (GIF only)
        self._loop_check = QCheckBox(self._lang.get("gif_video_loop", "Loop forever"))
        self._loop_check.setChecked(True)
        slay.addWidget(self._loop_check)
        return settings

    def _on_format_changed(self, text):
        is_gif = text == "GIF"
        self._loop_check.setVisible(is_gif)
        # Update extension in path
        path = self._path_edit.text()
        if path:
            ext = ".gif" if is_gif else ".mp4"
            if path == self._auto_output:
                self._auto_output = self._suggested_output(ext)
                self._path_edit.setText(self._auto_output)
            else:
                self._path_edit.setText(str(Path(path).with_suffix(ext)))

    def _suggested_output(self, ext: str) -> str:
        """A free ``output<ext>`` beside the first frame, so an earlier result is kept."""
        return str(free_names(Path(self._paths[0]).parent, ["output"], ext)[0])

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
        picked = save_path_into(
            self, self._path_edit, self._lang.get("gif_video_save", "Save As"), f"{fmt} (*{ext})")
        if picked:
            self._browsed_path = picked

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
        if not paths or not may_replace(self, output, self._browsed_path):
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
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_progress(self, current, total):
        self._progress.setValue(current)
        self._status_label.setText(f"{current}/{total}")

    def _cleanup_worker(self):
        self._worker = None

    def _on_cancel(self):
        """Stop an in-flight encode before rejecting.

        Cancel used to call ``reject`` directly while ``_CreateWorker`` kept
        encoding the GIF/MP4 to completion. Signal the abort first (without
        blocking the UI) so the loop stops before the next frame.
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.abort()
        self.reject()


    def _on_finished(self, success, message):
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)

        if success:
            msg = self._lang.get("gif_video_done", "Created: {path}").format(path=message)
            self._status_label.setText(msg)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(msg)
            call_later(0, self, self.accept)
        else:
            text = self._lang.get("generic_error", "Error: {error}").format(error=message)
            self._status_label.setText(text)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(text)


def open_gif_video_dialog(main_gui: GPUImageView):
    paths = selected_in_view_order(main_gui)
    if not paths:
        return
    dlg = GifVideoDialog(main_gui, paths)
    dlg.exec()
