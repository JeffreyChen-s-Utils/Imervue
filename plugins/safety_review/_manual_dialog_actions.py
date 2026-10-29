"""Dataset export and apply actions of the safety_review manual editor.

``_ManualReviewActionsMixin`` remembers the dataset folder, exports the
current image with its hand-labelled boxes as a YOLO sample, and censors the
drawn boxes into the output file. It is mixed into ``ManualReviewDialog``
(:mod:`_manual_dialog`), which owns the widgets these methods read.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from safety_review._detection import _process_manual_image
from safety_review._runner import _batch_destination

logger = logging.getLogger("Imervue.plugin.safety_review")


class _ManualReviewActionsMixin:
    """Dataset folder, dataset export and apply for ``ManualReviewDialog``."""

    _DATASET_SETTING = "safety_review_dataset_dir"

    def _dataset_dir(self):
        """Remembered dataset folder, prompting for one the first time."""
        from Imervue.user_settings.user_setting_dict import (
            schedule_save,
            user_setting_dict,
        )
        remembered = user_setting_dict.get(self._DATASET_SETTING)
        if remembered and os.path.isdir(remembered):
            return remembered
        path = QFileDialog.getExistingDirectory(
            self, self._lang.get("safety_review_dataset_dir", "Dataset folder"))
        if path:
            user_setting_dict[self._DATASET_SETTING] = path
            schedule_save()
            return path
        return None

    def _add_to_dataset(self):
        """Export the current image + hand-labelled boxes as a YOLO sample."""
        from safety_review._class_config import get_classes
        from safety_review._dataset import export_label
        dataset_dir = self._dataset_dir()
        if not dataset_dir:
            return
        iw, ih = self._canvas.image_size()
        try:
            count = export_label(dataset_dir, self._image_path,
                                 self._canvas.labeled_regions(), iw, ih,
                                 get_classes())
        except OSError:
            logger.error("Dataset export failed", exc_info=True)
            return
        if hasattr(self._gui.main_window, "toast"):
            self._gui.main_window.toast.success(
                self._lang.get("safety_review_dataset_added",
                               "Added to dataset ({count} labels)").format(
                                   count=count))

    def _output_path(self) -> str:
        if self._overwrite_check.isChecked():
            return self._image_path
        # Numbered like a batch run's output, so a second pass keeps the first result.
        return _batch_destination(self._image_path, str(Path(self._image_path).parent),
                                  False, None)

    def _apply(self):
        regions = self._canvas.regions()
        if not regions:
            return
        try:
            _process_manual_image(
                self._image_path, self._output_path(), regions,
                self._block_spin.value(),
                style=self._style_combo.currentData(),
                shape=self._shape_combo.currentData())
        except Exception:
            logger.error("Manual censor apply failed", exc_info=True)
            return
        if self._overwrite_check.isChecked():
            from safety_review._dialogs import _reload_grid_or_deepzoom
            _reload_grid_or_deepzoom(self._gui)
        if hasattr(self._gui.main_window, "toast"):
            self._gui.main_window.toast.success(
                self._lang.get("safety_review_manual_done",
                               "Applied {count} censor region(s)").format(
                                   count=len(regions)))
        self.accept()
