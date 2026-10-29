"""
比對對話框的模式處理
Compare dialog mode handlers: side-by-side grid with synced zoom/pan, overlay,
difference and A|B split, plus the sliders that drive them.
"""
from __future__ import annotations

from Imervue.gpu_image_view.actions.compare_dialog_image_label import _ImageLabel
from Imervue.gpu_image_view.actions.compare_dialog_math import (
    _ndarray_to_qimage,
    compute_difference,
    compute_overlay,
)


class CompareModesMixin:
    """Mode handlers for ``CompareDialog``; uses its widgets, ``_warn`` and ``_load_pair``."""

    def _run_side_by_side(self, count: int) -> None:
        paths = self._selected_paths()
        if len(paths) < count:
            self._warn(
                "compare_need_n",
                "Select at least {n} images.",
                n=count,
            )
            return
        paths = paths[:count]

        # Clear previous labels
        for lbl in self._sbs_labels:
            self._sbs_layout.removeWidget(lbl)
            lbl.deleteLater()
        self._sbs_labels.clear()

        _, cols = (1, 2) if count == 2 else (2, 2)
        for i, p in enumerate(paths):
            r, c = divmod(i, cols)
            lbl = _ImageLabel(p)
            lbl.view_changed.connect(
                lambda zoom, pan_x, pan_y, source=lbl: self._sync_sbs_labels(
                    source, zoom, pan_x, pan_y,
                )
            )
            self._sbs_layout.addWidget(lbl, r, c)
            self._sbs_labels.append(lbl)

        self._tabs.setCurrentWidget(self._sbs_widget)

    def _sync_sbs_labels(self, source: _ImageLabel, zoom: float,
                         pan_x: float, pan_y: float) -> None:
        for label in self._sbs_labels:
            if label is not source:
                label.sync_view(zoom, pan_x, pan_y)

    def _run_overlay(self) -> None:
        pair = self._load_pair()
        if pair is None:
            return
        self._overlay_arrs = pair
        self._refresh_overlay()
        self._tabs.setCurrentWidget(self._overlay_widget)

    def _on_overlay_slider(self, _val: int) -> None:
        if self._overlay_arrs is not None:
            self._refresh_overlay()

    def _refresh_overlay(self) -> None:
        if self._overlay_arrs is None:
            return
        alpha = self._overlay_slider.value() / 100.0
        a, b = self._overlay_arrs
        blended = compute_overlay(a, b, alpha)
        self._overlay_label.set_qimage(_ndarray_to_qimage(blended))

    def _run_difference(self) -> None:
        pair = self._load_pair()
        if pair is None:
            return
        self._diff_arrs = pair
        self._refresh_difference()
        self._tabs.setCurrentWidget(self._diff_widget)

    def _on_diff_slider(self, val: int) -> None:
        gain = val / 100.0
        self._diff_gain_label.setText(f"{gain:.1f}\u00d7")
        if self._diff_arrs is not None:
            self._refresh_difference()

    def _refresh_difference(self) -> None:
        if self._diff_arrs is None:
            return
        gain = self._diff_slider.value() / 100.0
        a, b = self._diff_arrs
        diff = compute_difference(a, b, gain)
        self._diff_label.set_qimage(_ndarray_to_qimage(diff))

    def _run_split(self) -> None:
        paths = self._selected_paths()
        if len(paths) != 2:
            self._warn("compare_need_two", "Select exactly 2 images.")
            return
        self._split_label.set_pair(paths[0], paths[1])
        self._split_slider.blockSignals(True)
        self._split_slider.setValue(int(self._split_label.split() * 100))
        self._split_slider.blockSignals(False)
        self._tabs.setCurrentWidget(self._split_widget)

    def _on_split_slider(self, val: int) -> None:
        self._split_label.set_split(val / 100.0)

    def _on_split_widget_changed(self, fraction: float) -> None:
        self._split_slider.blockSignals(True)
        self._split_slider.setValue(int(round(fraction * 100)))
        self._split_slider.blockSignals(False)
