"""Qt dialogs for the safety_review plugin.

Three user-facing dialogs (scan-all, single, batch) plus the shared
``_build_mode_row`` settings widget and the ``_ensure_deps`` dependency gate.
The dialogs are thin: they collect settings, kick off a worker from
``_workers`` and render its progress / result signals.
"""
from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.pip_installer import ensure_dependencies

from safety_review._constants import (
    ALL_CATEGORIES,
    CAT_GENITALIA,
    CAT_ANUS,
    CAT_NIPPLE,
    CAT_SEXUAL_ACT,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_CATEGORIES,
    DEFAULT_PADDING,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    REQUIRED_PACKAGES_ANIME,
    REQUIRED_PACKAGES_AUTO,
    REQUIRED_PACKAGES_REAL,
    STYLE_BLACK,
    STYLE_BLUR,
    STYLE_MOSAIC,
    _MODE_DEFAULTS,
)
from safety_review._detection import _scan_folder
from safety_review._workers import (
    _BatchWorker,
    _SingleWorker,
    _SubprocessBatchWorker,
    _SubprocessSingleWorker,
)

logger = logging.getLogger("Imervue.plugin.safety_review")

# Repeated language-key constants (declared once — SonarQube python:S1192).
_KEY_BROWSE = "export_browse"
_KEY_CANCEL = "export_cancel"
_KEY_OUTPUT_DIR = "safety_review_output_dir"
_KEY_INSTALLING = "safety_review_installing"
_KEY_INFO = "safety_review_info"
_KEY_RUN = "safety_review_run"
_KEY_BLOCK_SIZE = "safety_review_block_size"
_KEY_PADDING = "safety_review_padding"
_KEY_TIME = "safety_review_time"
_KEY_OVERWRITE = "safety_review_overwrite"
_KEY_SCAN_ALL_DONE = "safety_review_scan_all_done"
_KEY_BATCH_DONE = "safety_review_batch_done"

_DEFAULT_BROWSE = "Browse..."
_DEFAULT_INSTALLING = "Installing dependencies..."
_DEFAULT_INFO = (
    "Detects and mosaics exposed genitalia (male & female). "
    "Nipples are NOT mosaiced."
)
_DEFAULT_TIME = "Elapsed: {elapsed}    ETA: {eta}    (~{speed:.1f}s / image)"


def _ensure_deps(parent, on_ready, mode: str = MODE_REAL):
    if mode == MODE_AUTO:
        pkgs = REQUIRED_PACKAGES_AUTO
    elif mode == MODE_ANIME:
        pkgs = REQUIRED_PACKAGES_ANIME
    else:
        pkgs = REQUIRED_PACKAGES_REAL
    try:
        ensure_dependencies(parent, pkgs, on_ready)
    except Exception:
        logger.error("ensure_dependencies raised", exc_info=True)


def _fmt_time(seconds: float) -> str:
    """Format a duration in seconds as ``Hh MMm SSs`` (trimmed)."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def _selected_categories(cat_checks) -> frozenset[str]:
    return frozenset(cat for cat, cb in cat_checks.items() if cb.isChecked())


def _reload_grid_or_deepzoom(gui) -> None:
    """Refresh the tile grid or the current deep-zoom image after writes."""
    try:
        if gui.tile_grid_mode:
            gui.load_tile_grid_async(list(gui.model.images))
        elif gui.deep_zoom:
            images = gui.model.images
            if images and 0 <= gui.current_index < len(images):
                gui._clear_deep_zoom()
                gui.load_deep_zoom_image(images[gui.current_index])
    except Exception:
        logger.debug("Viewer reload failed", exc_info=True)


def _format_result_message(lang, success, failed, total_regions) -> str:
    """Build the completion summary, with or without a region count."""
    if total_regions >= 0:
        return lang.get(
            _KEY_SCAN_ALL_DONE,
            "Done — {success}/{total} images processed, "
            "{regions} region(s) mosaiced, {failed} failed.",
        ).format(
            success=success, total=success + failed,
            regions=total_regions, failed=failed,
        )
    return lang.get(
        _KEY_BATCH_DONE, "Processed {success}/{total} image(s)",
    ).format(success=success, total=success + failed)


def _build_mode_combo(layout, lang):
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel(lang.get("safety_review_mode", "Detection mode:")))
    mode_combo = QComboBox()
    mode_combo.addItem(lang.get("safety_review_mode_auto", "Auto"), MODE_AUTO)
    mode_combo.addItem(lang.get("safety_review_mode_real", "Real Photo"), MODE_REAL)
    mode_combo.addItem(
        lang.get("safety_review_mode_anime", "Anime / Illustration"), MODE_ANIME)
    mode_row.addWidget(mode_combo, 1)
    layout.addLayout(mode_row)
    return mode_combo


def _build_style_combo(layout, lang):
    style_row = QHBoxLayout()
    style_row.addWidget(QLabel(lang.get("safety_review_style", "Censor style:")))
    style_combo = QComboBox()
    style_combo.addItem(
        lang.get("safety_review_style_mosaic", "Mosaic"), STYLE_MOSAIC)
    style_combo.addItem(
        lang.get("safety_review_style_blur", "Gaussian Blur"), STYLE_BLUR)
    style_combo.addItem(
        lang.get("safety_review_style_black", "Black Bar"), STYLE_BLACK)
    style_row.addWidget(style_combo, 1)
    layout.addLayout(style_row)
    return style_combo


def _build_spin_row(layout, label_text, spin):
    row = QHBoxLayout()
    row.addWidget(QLabel(label_text))
    row.addWidget(spin)
    layout.addLayout(row)


def _build_category_checks(layout, lang):
    layout.addWidget(QLabel(
        lang.get("safety_review_categories", "Detection categories:")))
    cat_display = {
        CAT_GENITALIA: lang.get("safety_review_cat_genitalia",
                                "Genitalia (penis / vagina)"),
        CAT_ANUS: lang.get("safety_review_cat_anus", "Anus"),
        CAT_NIPPLE: lang.get("safety_review_cat_nipple", "Nipple / Breast"),
        CAT_SEXUAL_ACT: lang.get("safety_review_cat_sexual_act",
                                 "Sexual Act (anime only)"),
    }
    cat_checks: dict[str, QCheckBox] = {}
    cat_row = QHBoxLayout()
    for cat in ALL_CATEGORIES:
        cb = QCheckBox(cat_display[cat])
        cb.setChecked(cat in DEFAULT_CATEGORIES)
        cat_checks[cat] = cb
        cat_row.addWidget(cb)
    layout.addLayout(cat_row)
    return cat_checks


def _build_mode_row(layout, lang):
    """Add detection-mode combo, style combo, confidence, expand%,
    and category checkboxes to *layout*.

    Returns (mode_combo, conf_spin, expand_spin, style_combo, cat_checks).
    ``cat_checks`` is a dict  {category_name: QCheckBox}.
    """
    mode_combo = _build_mode_combo(layout, lang)
    style_combo = _build_style_combo(layout, lang)

    conf_spin = QDoubleSpinBox()
    conf_spin.setRange(0.01, 1.0)
    conf_spin.setSingleStep(0.05)
    conf_spin.setDecimals(2)
    conf_spin.setValue(_MODE_DEFAULTS[MODE_AUTO]["confidence"])
    _build_spin_row(
        layout, lang.get("safety_review_confidence", "Min confidence:"), conf_spin)

    expand_spin = QSpinBox()
    expand_spin.setRange(0, 200)
    expand_spin.setSingleStep(10)
    expand_spin.setValue(_MODE_DEFAULTS[MODE_AUTO]["expand_pct"])
    expand_spin.setSuffix("%")
    _build_spin_row(
        layout,
        lang.get("safety_review_expand_pct", "Expand detection box (%):"),
        expand_spin)

    cat_checks = _build_category_checks(layout, lang)

    def _on_mode_changed(index):
        mode = mode_combo.itemData(index)
        defaults = _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])
        conf_spin.setValue(defaults["confidence"])
        expand_spin.setValue(defaults["expand_pct"])
        sa_cb = cat_checks[CAT_SEXUAL_ACT]
        sa_cb.setEnabled(mode != MODE_REAL)
        if mode == MODE_REAL:
            sa_cb.setChecked(False)

    mode_combo.currentIndexChanged.connect(_on_mode_changed)
    _on_mode_changed(mode_combo.currentIndex())

    return mode_combo, conf_spin, expand_spin, style_combo, cat_checks


class _WorkerHostMixin:
    """Shared worker lifecycle: progress/time rendering and clean teardown."""

    def _render_time(self, current, time_args):
        if len(time_args) < 2:
            return
        elapsed, eta = time_args[0], time_args[1]
        eta_str = _fmt_time(eta) if current > 0 else "..."
        self._time_label.setText(
            self._lang.get(_KEY_TIME, _DEFAULT_TIME).format(
                elapsed=_fmt_time(elapsed),
                eta=eta_str,
                speed=elapsed / max(current, 1),
            )
        )

    def _cleanup(self):
        self._worker = None

    def _stop_worker(self):
        if self._worker and self._worker.isRunning():
            with contextlib.suppress(RuntimeError, TypeError):
                self._worker.disconnect()
            self._worker.wait(5000)
            self._worker = None

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)


class ScanAllDialog(_WorkerHostMixin, QDialog):
    """Scan folder dialog — user picks a folder, configures mode, then starts."""

    def __init__(self, main_gui,
                 initial_paths: list[str] | None = None,
                 block_size: int = DEFAULT_BLOCK_SIZE,
                 padding: int = DEFAULT_PADDING,
                 get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = initial_paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env
        self._block_size = block_size
        self._padding = padding
        self._finished = False

        self.setWindowTitle(
            self._lang.get("safety_review_scan_all_title",
                           "Safety Review — Scan All")
        )
        self.setMinimumWidth(500)
        self._build_ui()

        if self._paths:
            folder = str(Path(self._paths[0]).parent)
            self._folder_edit.setText(folder)
            self._update_count()

    def _build_folder_row(self, layout):
        layout.addWidget(QLabel(
            self._lang.get("safety_review_scan_folder", "Source folder:")))
        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText(
            self._lang.get("safety_review_scan_folder_hint",
                           "Choose a folder containing images..."))
        self._browse_folder_btn = QPushButton(
            self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        self._browse_folder_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(self._browse_folder_btn)
        layout.addLayout(folder_row)
        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _build_output_row(self, layout):
        self._overwrite_check = QCheckBox(
            self._lang.get(_KEY_OVERWRITE,
                           "Overwrite original files (no backup!)"))
        self._overwrite_check.setChecked(True)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        self._out_dir_label = QLabel(
            self._lang.get(_KEY_OUTPUT_DIR, "Output folder:"))
        self._out_dir_label.setVisible(False)
        layout.addWidget(self._out_dir_label)

        out_row = QHBoxLayout()
        self._out_dir_edit = QLineEdit()
        self._out_dir_edit.setVisible(False)
        self._out_browse_btn = QPushButton(
            self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        self._out_browse_btn.setVisible(False)
        self._out_browse_btn.clicked.connect(self._browse_out_dir)
        out_row.addWidget(self._out_dir_edit, 1)
        out_row.addWidget(self._out_browse_btn)
        layout.addLayout(out_row)

    def _build_progress_block(self, layout):
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        self._time_label = QLabel("")
        layout.addWidget(self._time_label)

    def _build_buttons(self, layout):
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton(self._lang.get(_KEY_CANCEL, "Cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("safety_review_start", "Start"))
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self._build_folder_row(layout)
        self._build_output_row(layout)
        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._build_progress_block(layout)
        self._build_buttons(layout)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("safety_review_scan_folder", "Source folder"))
        if folder:
            self._folder_edit.setText(folder)
            self._paths = _scan_folder(folder)
            self._update_count()
            if not self._out_dir_edit.text():
                self._out_dir_edit.setText(folder)

    def _browse_out_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get(_KEY_OUTPUT_DIR, "Output folder"))
        if folder:
            self._out_dir_edit.setText(folder)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get(
                "safety_review_scan_all_info",
                "Scanning {count} images — genitalia will be mosaiced, "
                "nipples will NOT be touched.",
            ).format(count=count)
        )
        self._start_btn.setEnabled(count > 0)

    def _on_overwrite_toggled(self, checked):
        self._out_dir_label.setVisible(not checked)
        self._out_dir_edit.setVisible(not checked)
        self._out_browse_btn.setVisible(not checked)

    def _on_mode_changed(self, index):
        mode = self._mode_combo.itemData(index)
        self._padding = _MODE_DEFAULTS.get(
            mode, _MODE_DEFAULTS[MODE_REAL])["padding"]

    def _lock_controls(self):
        for widget in (
            self._start_btn, self._browse_folder_btn, self._mode_combo,
            self._conf_spin, self._expand_spin, self._style_combo,
            self._overwrite_check,
        ):
            widget.setEnabled(False)
        for cb in self._cat_checks.values():
            cb.setEnabled(False)

    def _make_worker(self, output_dir, overwrite, mode, conf, expand, style,
                     categories):
        frozen_env = self._get_frozen_env() if self._get_frozen_env else None
        if frozen_env:
            python, sp = frozen_env
            return _SubprocessBatchWorker(
                python, sp, self._paths, output_dir,
                self._block_size, self._padding, overwrite=overwrite,
                mode=mode, confidence=conf, expand_pct=expand,
                style=style, categories=categories)
        return _BatchWorker(
            self._paths, output_dir,
            self._block_size, self._padding, overwrite=overwrite,
            mode=mode, confidence=conf, expand_pct=expand,
            style=style, categories=categories)

    def _start(self):
        if not self._paths:
            return
        overwrite = self._overwrite_check.isChecked()
        output_dir = None if overwrite else self._out_dir_edit.text().strip()
        if not overwrite and (not output_dir or not Path(output_dir).is_dir()):
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        mode = self._mode_combo.currentData()
        conf = self._conf_spin.value()
        expand = self._expand_spin.value()
        style = self._style_combo.currentData()
        categories = _selected_categories(self._cat_checks)

        self._lock_controls()
        self._status_label.setText(
            self._lang.get(_KEY_INSTALLING, _DEFAULT_INSTALLING))

        def _on_deps_ready():
            self._progress.setMaximum(len(self._paths))
            self._progress.setVisible(True)
            self._status_label.setText("")
            self._worker = self._make_worker(
                output_dir, overwrite, mode, conf, expand, style, categories)
            self._worker.progress.connect(self._on_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=mode)

    def _on_progress(self, current, total, name, *time_args):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")
        self._render_time(current, time_args)

    def _on_finished(self, success, failed, total_regions):
        self._finished = True
        self._progress.setValue(len(self._paths))
        msg = _format_result_message(self._lang, success, failed, total_regions)
        self._status_label.setText(msg)
        self._time_label.setText("")
        self._cancel_btn.setText(self._lang.get("safety_review_close", "Close"))
        self._start_btn.setVisible(False)

        if hasattr(self._gui.main_window, "toast"):
            toast = self._gui.main_window.toast
            (toast.info if failed else toast.success)(msg)

        if self._overwrite_check.isChecked():
            _reload_grid_or_deepzoom(self._gui)


class _SettingsDialogBase(_WorkerHostMixin, QDialog):
    """Common block-size / padding rows and overwrite wiring for the
    single + batch dialogs."""

    def _build_block_padding_rows(self, layout):
        self._block_spin = QSpinBox()
        self._block_spin.setRange(2, 64)
        self._block_spin.setValue(DEFAULT_BLOCK_SIZE)
        _build_spin_row(
            layout,
            self._lang.get(_KEY_BLOCK_SIZE, "Mosaic block size (px):"),
            self._block_spin)

        self._padding_spin = QSpinBox()
        self._padding_spin.setRange(0, 200)
        self._padding_spin.setValue(DEFAULT_PADDING)
        _build_spin_row(
            layout,
            self._lang.get(_KEY_PADDING, "Padding around region (px):"),
            self._padding_spin)

    def _on_mode_changed_padding(self, index):
        mode = self._mode_combo.itemData(index)
        self._padding_spin.setValue(
            _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])["padding"])

    def _collect_settings(self):
        return {
            "bs": self._block_spin.value(),
            "pad": self._padding_spin.value(),
            "mode": self._mode_combo.currentData(),
            "conf": self._conf_spin.value(),
            "expand": self._expand_spin.value(),
            "style": self._style_combo.currentData(),
            "categories": _selected_categories(self._cat_checks),
        }


class SafetyReviewDialog(_SettingsDialogBase):
    """Single-image dialog with settings."""

    def __init__(self, main_gui, image_path: str, get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env

        self.setWindowTitle(
            self._lang.get("safety_review_title", "Safety Review — Auto Mosaic")
        )
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_output_row(self, layout):
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        stem = Path(self._image_path).stem
        suffix = Path(self._image_path).suffix
        default_out = Path(self._image_path).parent / f"{stem}_censored{suffix}"
        self._path_edit.setText(str(default_out))
        browse_btn = QPushButton(self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._overwrite_check = QCheckBox(
            self._lang.get("safety_review_overwrite_single",
                           "Overwrite original file"))
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            self._lang.get("safety_review_source", "Source:")
            + f"  {Path(self._image_path).name}"
        ))
        info = QLabel(self._lang.get(_KEY_INFO, _DEFAULT_INFO))
        info.setWordWrap(True)
        layout.addWidget(info)

        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(
            self._on_mode_changed_padding)

        self._build_block_padding_rows(layout)
        self._build_output_row(layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, _SingleWorker.STEPS)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("%v / %m")
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get(_KEY_CANCEL, "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(self._lang.get(_KEY_RUN, "Apply Mosaic"))
        self._run_btn.clicked.connect(self._do_run)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _on_overwrite_toggled(self, checked):
        if checked:
            self._path_edit.setText(self._image_path)
        self._path_edit.setEnabled(not checked)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self._lang.get("export_save", "Save"),
            self._path_edit.text(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)")
        if path:
            self._path_edit.setText(path)

    def _make_worker(self, output, settings):
        frozen_env = self._get_frozen_env() if self._get_frozen_env else None
        if frozen_env:
            python, sp = frozen_env
            worker = _SubprocessSingleWorker(
                python, sp, self._image_path, output,
                settings["bs"], settings["pad"],
                mode=settings["mode"], confidence=settings["conf"],
                expand_pct=settings["expand"], style=settings["style"],
                categories=settings["categories"])
            worker.progress.connect(self._on_progress_text)
        else:
            worker = _SingleWorker(
                self._image_path, output, settings["bs"], settings["pad"],
                mode=settings["mode"], confidence=settings["conf"],
                expand_pct=settings["expand"], style=settings["style"],
                categories=settings["categories"])
            worker.progress.connect(self._on_progress_step)
        return worker

    def _do_run(self):
        output = self._path_edit.text().strip()
        if not output:
            return
        self._run_btn.setEnabled(False)
        self._status_label.setText(
            self._lang.get(_KEY_INSTALLING, _DEFAULT_INSTALLING))
        settings = self._collect_settings()

        def _on_deps_ready():
            self._progress_bar.setVisible(True)
            self._status_label.setText("")
            self._worker = self._make_worker(output, settings)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=settings["mode"])

    def _on_progress_step(self, step: int, msg: str):
        """From _SingleWorker (int, str)."""
        self._progress_bar.setValue(step)
        self._status_label.setText(msg)

    def _on_progress_text(self, msg: str):
        """From _SubprocessSingleWorker (str only)."""
        self._status_label.setText(msg)

    def _on_finished(self, ok: bool, result: str, count: int):
        self._progress_bar.setVisible(False)
        self._run_btn.setEnabled(True)
        if not ok:
            self._status_label.setText(f"Error: {result}")
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(f"Error: {result}")
            return

        if count == 0:
            text = self._lang.get(
                "safety_review_nothing",
                "No genitalia detected — image unchanged.")
        else:
            text = self._lang.get(
                "safety_review_done", "Done! Saved to: {path}"
            ).format(path=result)
        self._status_label.setText(text)
        if hasattr(self._gui.main_window, "toast"):
            self._gui.main_window.toast.success(
                self._lang.get("safety_review_done_short", "Mosaic applied!")
                if count else text)
        if self._overwrite_check.isChecked():
            _reload_grid_or_deepzoom(self._gui)
        QTimer.singleShot(500, self.accept)


class BatchSafetyReviewDialog(_SettingsDialogBase):
    """Batch dialog — selected images, choose overwrite or separate output."""

    def __init__(self, main_gui, paths: list[str], get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env

        self.setWindowTitle(
            self._lang.get("safety_review_batch_title", "Batch Safety Review")
        )
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_output_row(self, layout):
        self._overwrite_check = QCheckBox(
            self._lang.get(_KEY_OVERWRITE,
                           "Overwrite original files (no backup!)"))
        self._overwrite_check.setChecked(False)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        self._dir_label = QLabel(self._lang.get(_KEY_OUTPUT_DIR, "Output folder:"))
        layout.addWidget(self._dir_label)
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        if self._paths:
            self._dir_edit.setText(str(Path(self._paths[0]).parent))
        self._browse_btn = QPushButton(self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        self._browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(self._browse_btn)
        layout.addLayout(dir_row)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            self._lang.get("batch_export_count", "{count} image(s) selected")
            .format(count=len(self._paths))
        ))
        info = QLabel(self._lang.get(_KEY_INFO, _DEFAULT_INFO))
        info.setWordWrap(True)
        layout.addWidget(info)

        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(
            self._on_mode_changed_padding)

        self._build_block_padding_rows(layout)
        self._build_output_row(layout)

        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        self._time_label = QLabel("")
        layout.addWidget(self._time_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get(_KEY_CANCEL, "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(self._lang.get(_KEY_RUN, "Apply Mosaic"))
        self._run_btn.clicked.connect(self._do_run)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _on_overwrite_toggled(self, checked):
        self._dir_edit.setEnabled(not checked)
        self._browse_btn.setEnabled(not checked)
        self._dir_label.setEnabled(not checked)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get(_KEY_OUTPUT_DIR, "Output folder"))
        if folder:
            self._dir_edit.setText(folder)

    def _make_worker(self, output_dir, overwrite, settings):
        frozen_env = self._get_frozen_env() if self._get_frozen_env else None
        if frozen_env:
            python, sp = frozen_env
            return _SubprocessBatchWorker(
                python, sp, self._paths, output_dir,
                settings["bs"], settings["pad"], overwrite,
                mode=settings["mode"], confidence=settings["conf"],
                expand_pct=settings["expand"], style=settings["style"],
                categories=settings["categories"])
        return _BatchWorker(
            self._paths, output_dir, settings["bs"], settings["pad"], overwrite,
            mode=settings["mode"], confidence=settings["conf"],
            expand_pct=settings["expand"], style=settings["style"],
            categories=settings["categories"])

    def _do_run(self):
        overwrite = self._overwrite_check.isChecked()
        output_dir = self._dir_edit.text().strip()
        if not overwrite and (not output_dir or not Path(output_dir).is_dir()):
            return
        self._run_btn.setEnabled(False)
        self._status_label.setText(
            self._lang.get(_KEY_INSTALLING, _DEFAULT_INSTALLING))
        settings = self._collect_settings()

        def _on_deps_ready():
            self._progress.setVisible(True)
            self._progress.setMaximum(len(self._paths))
            self._progress.setValue(0)
            self._status_label.setText("")
            self._worker = self._make_worker(output_dir, overwrite, settings)
            self._worker.progress.connect(self._on_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=settings["mode"])

    def _on_progress(self, current, total, name, *time_args):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")
        self._render_time(current, time_args)

    def _on_finished(self, success, failed, total_regions):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._time_label.setText("")
        msg = _format_result_message(self._lang, success, failed, total_regions)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            toast = self._gui.main_window.toast
            (toast.info if failed else toast.success)(msg)

        if self._overwrite_check.isChecked():
            _reload_grid_or_deepzoom(self._gui)
        QTimer.singleShot(500, self.accept)
