"""
進階過濾對話框
Advanced filter — size / orientation / date-range.

Invoked from Filter menu. Filters the viewer's current image list against
user-specified criteria without modifying the underlying folder.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from collections.abc import Iterable

from PIL import Image
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


@dataclass(frozen=True)
class FilterCriteria:
    """Every field is optional; ``None`` means "don't restrict on this axis"."""
    min_width: int | None = None
    max_width: int | None = None
    min_height: int | None = None
    max_height: int | None = None
    min_size_kb: int | None = None
    max_size_kb: int | None = None
    orientation: str | None = None  # "landscape" | "portrait" | "square" | None
    after_date: datetime | None = None
    before_date: datetime | None = None

    def any_active(self) -> bool:
        return any(
            v is not None for v in (
                self.min_width, self.max_width,
                self.min_height, self.max_height,
                self.min_size_kb, self.max_size_kb,
                self.orientation, self.after_date, self.before_date,
            )
        )


def matches(path: str, criteria: FilterCriteria) -> bool:
    """Return True if ``path`` passes every active criterion."""
    if not criteria.any_active():
        return True
    try:
        stat = os.stat(path)
    except OSError:
        return False
    if not _matches_stat(stat, criteria):
        return False
    if not _needs_dimensions(criteria):
        return True
    dims = _read_dimensions(path)
    if dims is None:
        return False
    return _matches_dimensions(dims, criteria)


def _matches_stat(stat, criteria: FilterCriteria) -> bool:
    size_kb = stat.st_size / 1024
    if criteria.min_size_kb is not None and size_kb < criteria.min_size_kb:
        return False
    if criteria.max_size_kb is not None and size_kb > criteria.max_size_kb:
        return False
    mtime_dt = datetime.fromtimestamp(stat.st_mtime)
    if criteria.after_date is not None and mtime_dt < criteria.after_date:
        return False
    return not (criteria.before_date is not None and mtime_dt > criteria.before_date)


def _needs_dimensions(criteria: FilterCriteria) -> bool:
    return (
        criteria.min_width is not None or criteria.max_width is not None
        or criteria.min_height is not None or criteria.max_height is not None
        or criteria.orientation is not None
    )


def _read_dimensions(path: str) -> tuple[int, int] | None:
    try:
        with Image.open(path) as img:
            return img.size
    except (OSError, ValueError):
        return None


def _matches_dimensions(dims: tuple[int, int], criteria: FilterCriteria) -> bool:
    w, h = dims
    if criteria.min_width is not None and w < criteria.min_width:
        return False
    if criteria.max_width is not None and w > criteria.max_width:
        return False
    if criteria.min_height is not None and h < criteria.min_height:
        return False
    if criteria.max_height is not None and h > criteria.max_height:
        return False
    return _matches_orientation(w, h, criteria.orientation)


def _matches_orientation(w: int, h: int, orientation: str | None) -> bool:
    if orientation == "landscape":
        return w > h
    if orientation == "portrait":
        return h > w
    if orientation == "square":
        return w == h
    return True


def apply_filter(paths: Iterable[str], criteria: FilterCriteria) -> list[str]:
    return [p for p in paths if matches(p, criteria)]


class AdvancedFilterDialog(QDialog):
    """Collect filter criteria from the user; ``result()`` holds the choice."""

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        self._criteria: FilterCriteria | None = None

        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("adv_filter_title", "Advanced Filter"))
        self.resize(420, 380)

        root = QVBoxLayout(self)

        # -------- Resolution --------
        res_box = QGroupBox(lang.get("adv_filter_resolution", "Resolution (px)"))
        res_form = QFormLayout(res_box)
        self._min_w = _make_optional_spin()
        self._max_w = _make_optional_spin()
        self._min_h = _make_optional_spin()
        self._max_h = _make_optional_spin()
        res_form.addRow(lang.get("adv_filter_min_width", "Min width"), self._min_w)
        res_form.addRow(lang.get("adv_filter_max_width", "Max width"), self._max_w)
        res_form.addRow(lang.get("adv_filter_min_height", "Min height"), self._min_h)
        res_form.addRow(lang.get("adv_filter_max_height", "Max height"), self._max_h)
        root.addWidget(res_box)

        # -------- File size --------
        size_box = QGroupBox(lang.get("adv_filter_size", "File size (KB)"))
        size_form = QFormLayout(size_box)
        self._min_size = _make_optional_spin(maximum=10_000_000)
        self._max_size = _make_optional_spin(maximum=10_000_000)
        size_form.addRow(lang.get("adv_filter_min_size", "Min size"), self._min_size)
        size_form.addRow(lang.get("adv_filter_max_size", "Max size"), self._max_size)
        root.addWidget(size_box)

        # -------- Orientation --------
        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel(lang.get("adv_filter_orientation", "Orientation")))
        self._orient_combo = QComboBox()
        self._orient_combo.addItem(lang.get("adv_filter_orient_any", "Any"), None)
        self._orient_combo.addItem(
            lang.get("adv_filter_orient_landscape", "Landscape"), "landscape"
        )
        self._orient_combo.addItem(lang.get("adv_filter_orient_portrait", "Portrait"), "portrait")
        self._orient_combo.addItem(lang.get("adv_filter_orient_square", "Square"), "square")
        orient_row.addWidget(self._orient_combo)
        orient_row.addStretch(1)
        root.addLayout(orient_row)

        # -------- Date range --------
        date_box = QGroupBox(lang.get("adv_filter_date_range", "Modified date"))
        date_form = QFormLayout(date_box)
        self._after_enabled = QCheckBox()
        self._after_date = QDateEdit(QDate.currentDate().addYears(-1))
        self._after_date.setCalendarPopup(True)
        self._after_date.setEnabled(False)
        self._after_enabled.toggled.connect(self._after_date.setEnabled)
        after_row = QHBoxLayout()
        after_row.addWidget(self._after_enabled)
        after_row.addWidget(self._after_date)
        date_form.addRow(lang.get("adv_filter_after", "After"), _wrap(after_row))

        self._before_enabled = QCheckBox()
        self._before_date = QDateEdit(QDate.currentDate())
        self._before_date.setCalendarPopup(True)
        self._before_date.setEnabled(False)
        self._before_enabled.toggled.connect(self._before_date.setEnabled)
        before_row = QHBoxLayout()
        before_row.addWidget(self._before_enabled)
        before_row.addWidget(self._before_date)
        date_form.addRow(lang.get("adv_filter_before", "Before"), _wrap(before_row))
        root.addWidget(date_box)

        # -------- Buttons --------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def criteria(self) -> FilterCriteria | None:
        return self._criteria

    def _on_accept(self) -> None:
        self._criteria = FilterCriteria(
            min_width=_spin_value(self._min_w),
            max_width=_spin_value(self._max_w),
            min_height=_spin_value(self._min_h),
            max_height=_spin_value(self._max_h),
            min_size_kb=_spin_value(self._min_size),
            max_size_kb=_spin_value(self._max_size),
            orientation=self._orient_combo.currentData(),
            after_date=(
                datetime(self._after_date.date().year(),
                         self._after_date.date().month(),
                         self._after_date.date().day())
                if self._after_enabled.isChecked() else None
            ),
            before_date=(
                datetime(self._before_date.date().year(),
                         self._before_date.date().month(),
                         self._before_date.date().day(),
                         23, 59, 59)
                if self._before_enabled.isChecked() else None
            ),
        )
        self.accept()


def _make_optional_spin(maximum: int = 99999) -> QSpinBox:
    sb = QSpinBox()
    sb.setMinimum(0)
    sb.setMaximum(maximum)
    sb.setSpecialValueText("—")  # 0 displays as "—" (meaning unset)
    sb.setValue(0)
    return sb


def _spin_value(sb: QSpinBox) -> int | None:
    v = sb.value()
    return None if v == 0 else v


def _wrap(layout):
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    w.setLayout(layout)
    return w


def open_advanced_filter(main_window: ImervueMainWindow) -> None:
    """Show the dialog, apply the filter, and reload the grid on accept."""
    viewer = main_window.viewer
    if not viewer.model.images:
        return
    dlg = AdvancedFilterDialog(main_window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    criteria = dlg.criteria()
    if criteria is None or not criteria.any_active():
        return

    # Store unfiltered list so "Clear Filter" can restore
    if not getattr(viewer, "_unfiltered_images", None):
        viewer._unfiltered_images = list(viewer.model.images)

    filtered = apply_filter(viewer._unfiltered_images, criteria)
    lang = language_wrapper.language_word_dict
    if not filtered:
        if hasattr(main_window, "toast"):
            main_window.toast.warning(
                lang.get("adv_filter_no_results", "No images match the filter")
            )
        return

    viewer.clear_tile_grid()
    viewer.load_tile_grid_async(filtered)
    if hasattr(main_window, "toast"):
        main_window.toast.info(
            lang.get("adv_filter_applied", "Filter applied: {n} images")
                .format(n=len(filtered))
        )
