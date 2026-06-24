"""
Culling dialog — filter by pick/reject/unflagged state and bulk-delete rejects.

flag-based cull flow: user marks images P (pick) or Shift+X (reject), then
opens this dialog to isolate one group or trash all rejects in a single step.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QMessageBox,
)

from Imervue.library import image_index
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.culling_dialog")

_FILTER_VALUES = ("all", "pick", "reject", "unflagged")
_SIMILAR_THRESHOLD = 5  # max Hamming distance for grouping near-duplicates


class _AutoCullWorker(QThread):
    """Group near-duplicates, score by sharpness, and plan picks/rejects."""

    done = Signal(list, list)

    def __init__(self, paths: list[str], threshold: int):
        super().__init__()
        self._paths = paths
        self._threshold = threshold

    def run(self) -> None:  # pragma: no cover - background I/O
        from Imervue.gui._apply_save import load_rgba
        from Imervue.image.perceptual_hash import find_similar
        from Imervue.image.sharpness import sharpness_score
        from Imervue.library.group_cull import plan_cull_for_paths
        try:
            picks, rejects = plan_cull_for_paths(
                self._paths,
                group_fn=lambda paths: find_similar(paths, self._threshold),
                score_fn=lambda path: sharpness_score(load_rgba(path)),
            )
        except (OSError, ValueError) as exc:
            logger.exception("Auto-cull failed: %s", exc)
            picks, rejects = [], []
        self.done.emit(picks, rejects)


class CullingDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._worker: _AutoCullWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("culling_title", "Culling"))
        self.resize(420, 260)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("culling_explain",
                     "Filter the current folder by cull state, or permanently "
                     "delete all rejected images to disk.")
        ))

        layout.addWidget(QLabel(lang.get("culling_filter_by", "Show:")))
        self._group = QButtonGroup(self)
        radio_row = QHBoxLayout()
        labels = {
            "all": lang.get("culling_show_all", "All"),
            "pick": lang.get("culling_show_pick", "Picks only"),
            "reject": lang.get("culling_show_reject", "Rejects only"),
            "unflagged": lang.get("culling_show_unflagged", "Unflagged only"),
        }
        self._radios: dict[str, QRadioButton] = {}
        for value in _FILTER_VALUES:
            r = QRadioButton(labels[value])
            self._group.addButton(r)
            radio_row.addWidget(r)
            self._radios[value] = r
        self._radios["all"].setChecked(True)
        layout.addLayout(radio_row)

        apply_btn = QPushButton(lang.get("culling_apply_filter", "Apply filter"))
        apply_btn.clicked.connect(self._apply_filter)
        layout.addWidget(apply_btn)

        layout.addSpacing(12)
        layout.addWidget(QLabel(lang.get("culling_auto_label", "Auto-cull:")))
        self._auto_btn = QPushButton(
            lang.get("culling_auto_pick", "Pick sharpest per similar group"),
        )
        self._auto_btn.clicked.connect(self._auto_cull)
        layout.addWidget(self._auto_btn)

        layout.addSpacing(12)
        layout.addWidget(QLabel(
            lang.get("culling_delete_label", "Danger zone:")
        ))
        del_btn = QPushButton(lang.get("culling_delete_rejects", "Delete all rejects"))
        del_btn.clicked.connect(self._delete_rejects)
        layout.addWidget(del_btn)

        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _selected_state(self) -> str:
        for value, radio in self._radios.items():
            if radio.isChecked():
                return value
        return "all"

    def _apply_filter(self) -> None:
        state = self._selected_state()
        viewer = self._ui.viewer
        base = getattr(viewer, "_unfiltered_images", None) or list(viewer.model.images)
        filtered = list(base) if state == "all" else image_index.filter_by_cull(base, state)
        if not filtered:
            if hasattr(self._ui, "toast"):
                self._ui.toast.info(
                    language_wrapper.language_word_dict.get(
                        "culling_no_match", "No images in that cull state"
                    )
                )
            return
        viewer._unfiltered_images = list(base)
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(filtered)
        self.accept()

    def _toast(self, key: str, fallback: str, **fmt) -> None:  # pragma: no cover
        toast = getattr(self._ui, "toast", None)
        if toast is None:
            return
        text = language_wrapper.language_word_dict.get(key, fallback)
        toast.info(text.format(**fmt) if fmt else text)

    def _auto_cull(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        viewer = self._ui.viewer
        base = getattr(viewer, "_unfiltered_images", None) or list(viewer.model.images)
        if not base:
            self._toast("culling_no_images", "No images to cull")
            return
        self._auto_btn.setEnabled(False)
        self._worker = _AutoCullWorker(list(base), _SIMILAR_THRESHOLD)
        self._worker.done.connect(self._on_auto_cull_done)
        self._worker.start()

    def _on_auto_cull_done(self, picks: list, rejects: list) -> None:  # pragma: no cover
        self._worker = None
        self._auto_btn.setEnabled(True)
        for path in picks:
            image_index.set_cull_state(path, "pick")
        for path in rejects:
            image_index.set_cull_state(path, "reject")
        if picks or rejects:
            self._toast("culling_auto_done", "Picked {p}, rejected {r}",
                        p=len(picks), r=len(rejects))
        else:
            self._toast("culling_auto_none", "No similar groups found")

    def _delete_rejects(self) -> None:
        viewer = self._ui.viewer
        base = getattr(viewer, "_unfiltered_images", None) or list(viewer.model.images)
        rejects = image_index.filter_by_cull(base, "reject")
        if not rejects:
            QMessageBox.information(
                self, "",
                language_wrapper.language_word_dict.get(
                    "culling_no_rejects", "No rejected images to delete"
                )
            )
            return
        confirm = QMessageBox.question(
            self, "",
            language_wrapper.language_word_dict.get(
                "culling_confirm_delete",
                "Permanently delete {n} rejected image(s) from disk?"
            ).format(n=len(rejects)),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        deleted = self._delete_paths(rejects)
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                language_wrapper.language_word_dict.get(
                    "culling_deleted_toast", "Deleted {n} reject(s)"
                ).format(n=deleted)
            )
        reject_set = set(rejects)
        remaining = [p for p in base if p not in reject_set]
        viewer._unfiltered_images = None
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(remaining)
        self.accept()

    @staticmethod
    def _delete_paths(paths: list[str]) -> int:
        deleted = 0
        for p in paths:
            try:
                os.remove(p)
                image_index.set_cull_state(p, "unflagged")
                deleted += 1
            except OSError:
                continue
        return deleted


def open_culling(ui: ImervueMainWindow) -> None:
    CullingDialog(ui).exec()
