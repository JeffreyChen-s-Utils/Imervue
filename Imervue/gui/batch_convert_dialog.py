"""
批次格式轉換
Batch Convert — one-click format conversion for entire folders or selections.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)
from Imervue.system.image_listing import list_images
from Imervue.gui.export_source import upright_image
from Imervue.image.export_metadata import METADATA_ALL, export_save_options
from Imervue.image.formats import JPEG_EXTENSIONS, RAW_EXTENSIONS, STILL_IMAGE_EXTENSIONS
from Imervue.image.in_place_save import frame_count
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.gui.dialog_rows import action_button_row, path_browse_row, quality_slider
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.image.save_formats import (
    FORMAT_EXTENSIONS,
    QUALITY_FORMATS,
    available_formats,
    save_image,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.best_effort import best_effort
from Imervue.system.file_transfer import follow_saved_data

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.batch_convert")

_IMAGE_EXTS = frozenset({
    ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif", ".apng",
}) | JPEG_EXTENSIONS


def _scan_folder(folder: str) -> list[str]:
    """The images in *folder* this tool converts, in natural name order."""
    return list_images(folder, _IMAGE_EXTS)


class _ConvertWorker(QThread):
    progress = Signal(int, int, str)  # current, total, filename
    result_ready = Signal(int, int, int)  # success, failed, skipped
    # {trashed original: its conversion}, for the saved data to follow on the GUI thread
    originals_replaced = Signal(dict)

    def __init__(self, paths: list[str], output_dir: str, fmt: str,
                 quality: int, delete_originals: bool, skip_same_fmt: bool):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._fmt = fmt
        self._quality = quality
        self._delete_originals = delete_originals
        self._skip_same_fmt = skip_same_fmt

    def run(self):
        target_ext = FORMAT_EXTENSIONS.get(self._fmt, ".png")
        success = 0
        failed = 0
        skipped = 0
        converted: dict[str, str] = {}
        total = len(self._paths)
        for i, src in enumerate(self._paths):
            if self.isInterruptionRequested():
                break
            self.progress.emit(i, total, Path(src).name)
            try:
                if self._should_skip(src, target_ext):
                    skipped += 1
                    continue
                out_path = self._convert_one(src, target_ext)
                success += 1
                if self._may_delete(src, out_path):
                    converted[src] = out_path
            except IMAGE_READ_ERRORS as exc:
                logger.exception("Batch convert failed for %s: %s", src, exc)
                failed += 1
        trashed = self._trash_originals(list(converted))
        if trashed:
            self.originals_replaced.emit({src: converted[src] for src in trashed})
        self.result_ready.emit(success, failed, skipped)

    def _should_skip(self, src: str, target_ext: str) -> bool:
        if not self._skip_same_fmt:
            return False
        src_ext = Path(src).suffix.lower()
        if src_ext == target_ext:
            return True
        return src_ext in JPEG_EXTENSIONS and target_ext in JPEG_EXTENSIONS

    def _convert_one(self, src: str, target_ext: str) -> str:
        """Write *src* in the target format and return the new file's path.

        The viewer's decode — camera RAW developed at full size, sRGB, upright —
        with the source's EXIF carried over (without the orientation, which is
        baked into the pixels).
        """
        img = upright_image(src)
        out_path = self._resolve_output_path(src, target_ext)
        quality = self._quality if self._fmt in QUALITY_FORMATS else None
        save_image(img, str(out_path), self._fmt, quality,
                   export_save_options(src, METADATA_ALL))
        return str(out_path)

    def _resolve_output_path(self, src: str, target_ext: str) -> Path:
        out_path = Path(self._output_dir) / (Path(src).stem + target_ext)
        if not (out_path.exists() and str(out_path) != src):
            return out_path
        counter = 1
        while out_path.exists():
            out_path = Path(self._output_dir) / f"{Path(src).stem}_{counter}{target_ext}"
            counter += 1
        return out_path

    def _may_delete(self, src: str, out_path: str) -> bool:
        """Whether the original may go to the trash once *out_path* holds its conversion.

        Not when the conversion replaced it; not for an SVG or a video, which
        come out as one raster frame; and not for an animated or multi-page
        original, of which only the first frame was converted.
        """
        if not self._delete_originals or os.path.normpath(out_path) == os.path.normpath(src):
            return False
        ext = Path(src).suffix.lower()
        if ext == ".svg" or ext not in STILL_IMAGE_EXTENSIONS:
            logger.info("Keeping %s: its conversion is a single raster image", src)
            return False
        try:
            frames = frame_count(src)
        except IMAGE_READ_ERRORS:
            # Converted through another decoder: libraw reads a RAW Pillow can't.
            return ext in RAW_EXTENSIONS
        if frames > 1:
            logger.info("Keeping %s: only its first frame was converted", src)
            return False
        return True

    @staticmethod
    def _trash_originals(paths: list[str]) -> list[str]:
        """Send the converted originals to the recycle bin in one batch; returns those trashed."""
        if not paths:
            return []
        from Imervue.system.trash_ops import trash_batch
        trashed, failed = trash_batch(paths)
        for path in failed:
            logger.warning("Could not move the converted original %s to the trash", path)
        return trashed


class BatchConvertDialog(WorkerHostMixin, QDialog):
    def __init__(self, main_gui: GPUImageView, paths: list[str] | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(
            self._lang.get("batch_convert_title", "Batch Format Conversion"))
        self.setMinimumWidth(500)
        self._build_ui()

        if self._paths:
            folder = str(Path(self._paths[0]).parent)
            self._src_edit.setText(folder)
            self._out_edit.setText(folder)
            self._update_count()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        browse_text = self._lang.get("export_browse", "Browse...")

        # Source folder
        layout.addWidget(QLabel(
            self._lang.get("batch_convert_source", "Source folder:")))
        src_row, self._src_edit, _src_browse = path_browse_row(
            self._browse_src, browse_text=browse_text)
        self._src_edit.setPlaceholderText(
            self._lang.get("batch_convert_source_hint",
                           "Choose a folder with images..."))
        layout.addLayout(src_row)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        layout.addLayout(self._build_format_row())

        # Quality
        self._quality_label, self._quality_slider = quality_slider(self._lang)
        self._quality_slider.setToolTip(self._lang.get(
            "batch_convert_quality_tooltip",
            "Compression quality (0 worst / smallest, 100 best / "
            "largest). Ignored for lossless formats like PNG.",
        ))
        layout.addWidget(self._quality_label)
        layout.addWidget(self._quality_slider)

        self._add_option_checks(layout)
        self._add_output_rows(layout, browse_text)

        # Progress
        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("batch_convert_start", "Convert"))
        self._start_btn.clicked.connect(self._do_convert)
        layout.addLayout(action_button_row(cancel_btn, self._start_btn))

        self._on_format_changed()

    def _build_format_row(self) -> QHBoxLayout:
        """Target-format combo, WebP preselected."""
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(
            self._lang.get("batch_convert_format", "Convert to:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(available_formats())
        self._fmt_combo.setCurrentText("WebP")
        self._fmt_combo.currentTextChanged.connect(self._on_format_changed)
        self._fmt_combo.setToolTip(self._lang.get(
            "batch_convert_format_tooltip",
            "Output container — WebP is the highest-quality lossy "
            "modern format; PNG is lossless; JPEG smallest at the "
            "cost of compression artefacts.",
        ))
        fmt_row.addWidget(self._fmt_combo, 1)
        return fmt_row

    def _add_option_checks(self, layout: QVBoxLayout) -> None:
        """Skip-same-format (on) and delete-originals (off) boxes."""
        self._skip_same = QCheckBox(
            self._lang.get("batch_convert_skip_same",
                           "Skip images already in target format"))
        self._skip_same.setChecked(True)
        self._skip_same.setToolTip(self._lang.get(
            "batch_convert_skip_same_tooltip",
            "Don't re-encode files that already use the chosen format "
            "— saves time and avoids quality loss from a re-encode.",
        ))
        layout.addWidget(self._skip_same)

        self._delete_orig = QCheckBox(
            self._lang.get("batch_convert_delete_orig",
                           "Delete original files after conversion"))
        self._delete_orig.setChecked(False)
        self._delete_orig.setToolTip(self._lang.get(
            "batch_convert_delete_orig_tooltip",
            "Move originals to recycle bin after a successful "
            "convert. Off (default) keeps them so a botched convert "
            "doesn't lose data.",
        ))
        layout.addWidget(self._delete_orig)

    def _add_output_rows(self, layout: QVBoxLayout, browse_text: str) -> None:
        """Same-folder toggle, then the output label and row it keeps hidden while checked."""
        self._same_dir_check = QCheckBox(
            self._lang.get("batch_convert_same_dir",
                           "Save to same folder as source"))
        self._same_dir_check.setChecked(True)
        self._same_dir_check.toggled.connect(self._on_same_dir_toggled)
        layout.addWidget(self._same_dir_check)

        self._out_label = QLabel(
            self._lang.get("batch_convert_output", "Output folder:"))
        self._out_label.setVisible(False)
        layout.addWidget(self._out_label)
        out_row, self._out_edit, self._out_browse = path_browse_row(
            self._browse_out, browse_text=browse_text)
        self._out_edit.setVisible(False)
        self._out_browse.setVisible(False)
        layout.addLayout(out_row)

    def _browse_src(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("batch_convert_source", "Source folder"))
        if folder:
            self._src_edit.setText(folder)
            self._paths = _scan_folder(folder)
            self._update_count()
            if self._same_dir_check.isChecked():
                self._out_edit.setText(folder)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("batch_convert_output", "Output folder"))
        if folder:
            self._out_edit.setText(folder)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get("batch_convert_count",
                           "{count} image(s) found").format(count=count))
        self._start_btn.setEnabled(count > 0)

    def _on_format_changed(self, _text=None):
        visible = self._fmt_combo.currentText() in QUALITY_FORMATS
        self._quality_label.setVisible(visible)
        self._quality_slider.setVisible(visible)

    def _on_same_dir_toggled(self, checked):
        self._out_label.setVisible(not checked)
        self._out_edit.setVisible(not checked)
        self._out_browse.setVisible(not checked)

    def _do_convert(self):
        if not self._paths:
            return

        if self._same_dir_check.isChecked():
            output_dir = self._src_edit.text().strip()
        else:
            output_dir = self._out_edit.text().strip()
        if not output_dir:
            return
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self._start_btn.setEnabled(False)
        self._progress.setMaximum(len(self._paths))
        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._worker = _ConvertWorker(
            self._paths, output_dir,
            self._fmt_combo.currentText(),
            self._quality_slider.value(),
            self._delete_orig.isChecked(),
            self._skip_same.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.originals_replaced.connect(self._on_originals_replaced)
        self._worker.finished.connect(self._cleanup)
        self._worker.start()

    def _on_progress(self, current, total, name):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")

    def _cleanup(self):
        self._worker = None

    def _on_originals_replaced(self, replaced: dict) -> None:
        # A bound method, so the queued signal runs this on the GUI thread. The
        # conversion took the trashed original's place: its rating, tags and
        # library notes move over, as a rename would carry them.
        follow_saved_data(replaced)

    def _on_finished(self, success, failed, skipped):
        self._progress.setValue(len(self._paths))
        self._start_btn.setEnabled(True)

        msg = self._lang.get(
            "batch_convert_done",
            "Done — {success} converted, {skipped} skipped, {failed} failed."
        ).format(success=success, skipped=skipped, failed=failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        # Reload viewer if converted in-place
        if self._same_dir_check.isChecked():
            with best_effort("reload the tile grid after converting", logger):
                if self._gui.tile_grid_mode:
                    self._gui.load_tile_grid_async(list(self._gui.model.images))



def open_batch_convert(main_gui: GPUImageView):
    """Open batch convert from current folder images."""
    paths = list(main_gui.model.images) if main_gui.model.images else None
    dlg = BatchConvertDialog(main_gui, paths=paths)
    dlg.exec()
