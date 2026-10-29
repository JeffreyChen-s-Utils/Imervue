"""
圖片比對對話框
Compare Images — side-by-side (2/4), overlay (alpha), and difference modes.

- Side-by-side: 2 or 4 tiles rendered in a grid, each auto-scaled.
- Overlay: two images stacked with a blend slider (0 = only A, 100 = only B).
- Difference: per-pixel abs(A - B), gain-boosted so subtle changes stand out.

All modes reuse ``_SyncLabel`` as the display surface so we can extend them
with synced zoom/pan later without touching the mode code.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QWidget,
    QTabWidget, QSlider, QMessageBox,
)

from Imervue.gpu_image_view.actions.compare_dialog_image_label import _ImageLabel
from Imervue.gpu_image_view.actions.compare_dialog_math import (
    _load_rgba_array,
    _match_sizes,
    _ndarray_to_qimage,
    compute_difference,
    compute_overlay,
)
from Imervue.gpu_image_view.actions.compare_dialog_modes import CompareModesMixin
from Imervue.gpu_image_view.actions.compare_dialog_split_label import (
    _draw_split_handle,
    _SplitLabel,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# The views and image math live in sibling modules; this stays their import path.
__all__ = [
    "CompareDialog",
    "_ImageLabel",
    "_SplitLabel",
    "_draw_split_handle",
    "_load_rgba_array",
    "_match_sizes",
    "_ndarray_to_qimage",
    "compute_difference",
    "compute_overlay",
    "open_compare_dialog",
    "preselected_paths",
]


# ===========================
# Dialog
# ===========================

class CompareDialog(CompareModesMixin, QDialog):

    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui
        self._lang = language_wrapper.language_word_dict

        self.setWindowTitle(self._lang.get("compare_title", "Compare Images"))
        self.resize(1280, 820)

        root = QHBoxLayout(self)
        root.addLayout(self._build_picker_panel(main_gui.model.images), stretch=1)

        # ===== Right — tabbed display =====
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, stretch=3)
        self._add_side_by_side_tab()
        self._add_overlay_tab()
        self._add_difference_tab()
        self._add_split_tab()

        # Select 2 - 4 thumbnails, then Compare: the dialog opens on them.
        chosen = preselected_paths(main_gui)
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setSelected(item.data(Qt.ItemDataRole.UserRole) in chosen)
        if len(chosen) in (2, 4):
            self._run_side_by_side(len(chosen))

    def _build_picker_panel(self, paths: list[str]) -> QVBoxLayout:
        """Multi-select image list over the mode buttons."""
        left = QVBoxLayout()

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for path in paths:
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)
        left.addWidget(self._list)

        # Quick buttons: Side-by-side 2 / 4
        sbs_row = QHBoxLayout()
        btn_2 = QPushButton(self._lang.get("compare_2", "Side-by-side (2)"))
        btn_2.clicked.connect(lambda: self._run_side_by_side(2))
        sbs_row.addWidget(btn_2)
        btn_4 = QPushButton(self._lang.get("compare_4", "Side-by-side (4)"))
        btn_4.clicked.connect(lambda: self._run_side_by_side(4))
        sbs_row.addWidget(btn_4)
        left.addLayout(sbs_row)

        # Overlay / Difference / Split (each needs exactly 2 selections)
        for key, fallback, slot in (
            ("compare_overlay", "Overlay (2)", self._run_overlay),
            ("compare_difference", "Difference (2)", self._run_difference),
            ("compare_split", "A|B Split (2)", self._run_split),
        ):
            button = QPushButton(self._lang.get(key, fallback))
            button.clicked.connect(slot)
            left.addWidget(button)
        return left

    @staticmethod
    def _slider(lo: int, hi: int, value: int, on_change) -> QSlider:
        """Horizontal slider over ``[lo, hi]`` at ``value``, calling ``on_change`` on moves."""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        slider.valueChanged.connect(on_change)
        return slider

    @staticmethod
    def _slider_row(*widgets) -> QHBoxLayout:
        """Row of ``widgets``; the slider among them takes the stretch."""
        row = QHBoxLayout()
        for widget in widgets:
            row.addWidget(widget, stretch=1 if isinstance(widget, QSlider) else 0)
        return row

    def _add_view_tab(self, label: QWidget, controls: QHBoxLayout, title: str) -> QWidget:
        """Tab page with ``label`` stretching over its ``controls`` row."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label, stretch=1)
        layout.addLayout(controls)
        self._tabs.addTab(page, title)
        return page

    def _add_side_by_side_tab(self) -> None:
        """Grid the side-by-side labels are placed into when a comparison runs."""
        self._sbs_widget = QWidget()
        self._sbs_layout = QGridLayout(self._sbs_widget)
        self._sbs_layout.setSpacing(4)
        self._tabs.addTab(self._sbs_widget, self._lang.get("compare_tab_sbs", "Side-by-side"))
        self._sbs_labels: list[_ImageLabel] = []

    def _add_overlay_tab(self) -> None:
        """A / B blend with a 0–100 mix slider starting at 50."""
        self._overlay_label = _ImageLabel()
        self._overlay_slider = self._slider(0, 100, 50, self._on_overlay_slider)
        self._overlay_widget = self._add_view_tab(
            self._overlay_label,
            self._slider_row(QLabel("A"), self._overlay_slider, QLabel("B")),
            self._lang.get("compare_tab_overlay", "Overlay"),
        )
        self._overlay_arrs: tuple[np.ndarray, np.ndarray] | None = None

    def _add_difference_tab(self) -> None:
        """|A - B| view with a gain slider (0.10× … 20×) and its readout."""
        self._diff_label = _ImageLabel()
        self._diff_slider = self._slider(10, 2000, 100, self._on_diff_slider)
        self._diff_gain_label = QLabel("1.0×")
        self._diff_widget = self._add_view_tab(
            self._diff_label,
            self._slider_row(
                QLabel(self._lang.get("compare_gain", "Gain")),
                self._diff_slider, self._diff_gain_label,
            ),
            self._lang.get("compare_tab_difference", "Difference"),
        )
        self._diff_arrs: tuple[np.ndarray, np.ndarray] | None = None

    def _add_split_tab(self) -> None:
        """Before / after divider, draggable on the image or via the slider."""
        self._split_label = _SplitLabel()
        self._split_slider = self._slider(0, 100, 50, self._on_split_slider)
        self._split_label.split_changed.connect(self._on_split_widget_changed)
        self._split_widget = self._add_view_tab(
            self._split_label,
            self._slider_row(QLabel("A"), self._split_slider, QLabel("B")),
            self._lang.get("compare_tab_split", "A|B Split"),
        )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _selected_paths(self) -> list[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._list.selectedItems()
        ]

    def _warn(self, msg_key: str, fallback: str, **values) -> None:
        QMessageBox.information(
            self,
            self._lang.get("compare_title", "Compare Images"),
            self._lang.get(msg_key, fallback).format(**values),
        )

    def _load_pair(self) -> tuple[np.ndarray, np.ndarray] | None:
        paths = self._selected_paths()
        if len(paths) != 2:
            self._warn("compare_need_two", "Select exactly 2 images.")
            return None
        a = _load_rgba_array(paths[0])
        b = _load_rgba_array(paths[1])
        if a is None or b is None:
            self._warn("compare_load_failed", "Failed to load one of the images.")
            return None
        return a, b


def preselected_paths(main_gui) -> list[str]:
    """The thumbnails selected on the wall, in folder order: what the user asked to compare."""
    if not getattr(main_gui, "tile_selection_mode", False):
        return []
    chosen = set(getattr(main_gui, "selected_tiles", ()))
    return [path for path in main_gui.model.images if path in chosen]


def open_compare_dialog(main_gui: GPUImageView) -> None:
    dlg = CompareDialog(main_gui)
    dlg.exec()
