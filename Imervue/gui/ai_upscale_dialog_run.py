"""
AI 圖片放大對話框的執行流程
Run lifecycle of the AI upscale dialog, mixed into ``AIUpscaleDialog``.

Validates the options, launches the worker (behind the onnxruntime install
offer for the AI models), registers its retry factory with the background job
registry, and resets the controls, toasts and reloads the viewer when it ends.
"""
from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from Imervue.gui.ai_upscale_engine import REQUIRED_PACKAGES, _TRAD_PREFIX
from Imervue.gui.ai_upscale_worker import _UpscaleWorker
from Imervue.gui.background_jobs import job_registry
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue.ai_upscale")


class UpscaleRunMixin:
    """Start, progress and finish handling of ``AIUpscaleDialog``; adds no state."""

    def _do_start(self):
        if not self._paths:
            return

        overwrite = self._overwrite_check.isChecked()
        output_dir = "" if overwrite else self._out_edit.text().strip()
        if not overwrite:
            if not output_dir:
                return
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        model_key = self._model_combo.currentData()
        self._start_btn.setEnabled(False)
        self._model_combo.setEnabled(False)
        self._overwrite_check.setEnabled(False)

        def _launch_worker():
            self._progress.setMaximum(len(self._paths))
            self._progress.setValue(0)
            self._progress.setVisible(True)
            self._status_label.setText("")

            scale_override = (self._scale_spin.value()
                              if model_key.startswith(_TRAD_PREFIX) else 0)
            # Tile progress is only relevant for AI models
            self._tile_progress.setVisible(not model_key.startswith(_TRAD_PREFIX))

            self._worker = _UpscaleWorker(
                self._paths, output_dir, model_key, overwrite,
                scale_override=scale_override)
            job_registry().add(self._worker, self.windowTitle(),
                               partial(_UpscaleWorker, output_dir=output_dir, model_key=model_key,
                                       overwrite=overwrite, scale_override=scale_override))
            self._worker.progress.connect(self._on_progress)
            self._worker.tile_progress.connect(self._on_tile_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        if model_key.startswith(_TRAD_PREFIX):
            # Traditional methods need no extra dependencies.
            _launch_worker()
        else:
            self._status_label.setText(
                self._lang.get("upscale_installing",
                               "Installing dependencies..."))
            try:
                ensure_dependencies(
                    self._gui.main_window, REQUIRED_PACKAGES, _launch_worker)
            except Exception:
                logger.exception("ensure_dependencies raised")
                self._start_btn.setEnabled(True)

    def _on_progress(self, current, total, status):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {status}")

    def _on_tile_progress(self, done, total):
        self._tile_progress.setMaximum(total)
        self._tile_progress.setValue(done)

    def _cleanup(self):
        self._worker = None

    def _on_finished(self, success, failed):
        self._progress.setValue(len(self._paths))
        self._tile_progress.setVisible(False)
        self._start_btn.setEnabled(True)
        self._model_combo.setEnabled(True)
        self._overwrite_check.setEnabled(True)

        msg = self._lang.get(
            "upscale_done",
            "Done — {success} upscaled, {failed} failed."
        ).format(success=success, failed=failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        # Reload viewer if overwritten
        if self._overwrite_check.isChecked():
            with best_effort("reload the viewer after upscaling", logger):
                if self._gui.tile_grid_mode:
                    self._gui.load_tile_grid_async(list(self._gui.model.images))
                elif self._gui.deep_zoom:
                    images = self._gui.model.images
                    if images and 0 <= self._gui.current_index < len(images):
                        self._gui._clear_deep_zoom()
                        self._gui.load_deep_zoom_image(
                            images[self._gui.current_index])

