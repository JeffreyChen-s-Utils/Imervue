"""Run lifecycle of the safety_review Scan All dialog.

``_ScanAllRunMixin`` locks / unlocks the settings, builds the batch worker
(in-process or frozen-env subprocess), gates it on the dependency install and
renders its progress and summary. It is mixed into ``ScanAllDialog`` in
:mod:`_dialogs`, which owns the widgets these methods read.
"""
from __future__ import annotations

from pathlib import Path

from safety_review._constants import CAT_SEXUAL_ACT, MODE_REAL, SHAPE_PRECISE
from safety_review._dialogs_common import (
    _DEFAULT_INSTALLING,
    _KEY_INSTALLING,
    _ensure_deps,
    _format_result_message,
    _reload_grid_or_deepzoom,
    _selected_categories,
)
from safety_review._workers import _BatchWorker, _SubprocessBatchWorker


class _ScanAllRunMixin:
    """Settings lock, worker construction and progress for ``ScanAllDialog``."""

    def _lock_controls(self):
        for widget in self._controls():
            widget.setEnabled(False)
        for cb in self._cat_checks.values():
            cb.setEnabled(False)

    def _unlock_controls(self):
        """Re-enable the settings so the dialog is reusable for another run."""
        for widget in self._controls():
            widget.setEnabled(True)
        real = self._mode_combo.currentData() == MODE_REAL
        for cat, cb in self._cat_checks.items():
            cb.setEnabled(not (real and cat == CAT_SEXUAL_ACT))

    def _failed_folder(self) -> str | None:
        """Sibling ``<folder>_censor_failed`` dir that collects copies of the
        images that fail to process, mirroring their subfolder structure."""
        root = self._folder_edit.text().strip()
        if not root:
            return None
        base = Path(root)
        return str(base.parent / f"{base.name or 'scan'}_censor_failed")

    def _make_worker(self, output_dir, overwrite, *, mode, conf, expand, style,
                     categories, shape):
        # source_root and only-censored are only meaningful for a separate-
        # output run; on overwrite each file is written back in place.
        source_root = None if overwrite else self._source_root
        only_censored = (not overwrite) and self._only_censored_check.isChecked()
        # Failed images are always mirrored relative to the scanned folder,
        # independent of the output/overwrite choice.
        scan_root = self._folder_edit.text().strip() or None
        self._last_failed_dir = self._failed_folder()
        merge_regions = self._merge_check.isChecked()
        frozen_env = self._get_frozen_env() if self._get_frozen_env else None
        if frozen_env:
            python, sp = frozen_env
            return _SubprocessBatchWorker(
                python, sp, self._paths, output_dir,
                self._block_size, self._padding, overwrite=overwrite,
                mode=mode, confidence=conf, expand_pct=expand,
                style=style, categories=categories, source_root=source_root,
                only_censored=only_censored, shape=shape,
                failed_dir=self._last_failed_dir, scan_root=scan_root,
                merge_regions=merge_regions)
        return _BatchWorker(
            self._paths, output_dir,
            self._block_size, self._padding, overwrite=overwrite,
            mode=mode, confidence=conf, expand_pct=expand,
            style=style, categories=categories, source_root=source_root,
            only_censored=only_censored, shape=shape,
            failed_dir=self._last_failed_dir, scan_root=scan_root,
            merge_regions=merge_regions)

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
        shape = self._shape_combo.currentData()

        self._lock_controls()
        self._status_label.setText(
            self._lang.get(_KEY_INSTALLING, _DEFAULT_INSTALLING))

        def _on_deps_ready():
            self._progress.setMaximum(len(self._paths))
            self._progress.setVisible(True)
            self._status_label.setText("")
            self._worker = self._make_worker(
                output_dir, overwrite, mode=mode, conf=conf, expand=expand,
                style=style, categories=categories, shape=shape)
            self._worker.progress.connect(self._on_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=mode,
                     precise=(shape == SHAPE_PRECISE))

    def _on_progress(self, current, total, name, *time_args):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")
        self._render_time(current, time_args)

    def _on_finished(self, success, failed, total_regions):
        self._finished = True
        self._progress.setValue(len(self._paths))
        msg = _format_result_message(self._lang, success, failed, total_regions)
        if failed and self._last_failed_dir:
            msg += "\n" + self._lang.get(
                "safety_review_failed_folder",
                "{count} failed image(s) copied to: {path}",
            ).format(count=failed, path=self._last_failed_dir)
        self._status_label.setText(msg)
        self._time_label.setText("")
        # Reset to a ready state so the dialog can be reused for another run
        # (adjust settings / pick a new folder) instead of being reopened.
        self._unlock_controls()
        self._start_btn.setText(self._lang.get("safety_review_start", "Start"))
        self._start_btn.setVisible(True)

        if hasattr(self._gui.main_window, "toast"):
            toast = self._gui.main_window.toast
            (toast.info if failed else toast.success)(msg)

        if self._overwrite_check.isChecked():
            _reload_grid_or_deepzoom(self._gui)
