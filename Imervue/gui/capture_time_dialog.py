"""Extra Tools > Library & Metadata > Edit Capture Time: shift the EXIF capture time of a selection.

The "my camera clock was wrong" fix. Dial in the shift directly, or say when
the first photo was really taken and the shift follows; every selected photo
with an EXIF capture time moves by the same amount. The arithmetic and the
EXIF rewrite live in :mod:`Imervue.library.capture_time`; this is the Qt shell.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.gpu_image_view.actions.select import selection_or_all
from Imervue.library.capture_time import (
    delta_to_match,
    exif_capture_time,
    plan_exif_rewrites,
    write_capture_time,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_SHOWN = "%Y-%m-%d %H:%M:%S"
_QT_SHOWN = "yyyy-MM-dd HH:mm:ss"
# (attribute, label key, English label, ± range)
_PARTS = (
    ("_days", "capture_time_days", "Days", 36500),
    ("_hours", "capture_time_hours", "Hours", 23),
    ("_minutes", "capture_time_minutes", "Minutes", 59),
    ("_seconds", "capture_time_seconds", "Seconds", 59),
)


def read_capture_times(paths: list[str]) -> list[tuple[str, datetime]]:
    """``(path, EXIF capture time)`` for every path that has one, in order."""
    found = ((path, exif_capture_time(path)) for path in paths)
    return [(path, when) for path, when in found if when is not None]


def apply_shift(items: list[tuple[str, datetime]], delta: timedelta) -> tuple[int, int]:
    """Rewrite every item's capture time shifted by *delta*; returns ``(written, failed)``.

    Raises ``OverflowError`` before writing anything when a shifted time leaves
    the calendar.
    """
    written = failed = 0
    for path, text in plan_exif_rewrites(items, delta):
        if write_capture_time(path, text):
            written += 1
        else:
            failed += 1
    return written, failed


def split_delta(delta: timedelta) -> tuple[int, int, int, int]:
    """``(days, hours, minutes, seconds)`` of *delta*, every part carrying its sign."""
    sign = -1 if delta < timedelta(0) else 1
    total = int(abs(delta).total_seconds())
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return sign * days, sign * hours, sign * minutes, sign * seconds


class CaptureTimeDialog(QDialog):
    """Shift the EXIF capture time of *paths* by one amount."""

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("capture_time_title", "Edit Capture Time"))
        self._items = read_capture_times(paths)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "capture_time_source",
            "{count} photo(s) have an EXIF capture time; {skipped} without one are left alone.",
        ).format(count=len(self._items), skipped=len(paths) - len(self._items))))
        layout.addLayout(self._build_form(lang))
        self._preview = QLabel("")
        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._preview)
        layout.addWidget(self._status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply
                                   | QDialogButtonBox.StandardButton.Close)
        self._apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_btn.setEnabled(bool(self._items))
        self._apply_btn.clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._show_preview()

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        row = QHBoxLayout()
        for attr, key, label, limit in _PARTS:
            spin = QSpinBox()
            spin.setRange(-limit, limit)
            spin.setPrefix(lang.get(key, label) + " ")
            spin.valueChanged.connect(self._on_shift_edited)
            setattr(self, attr, spin)
            row.addWidget(spin)
        form.addRow(lang.get("capture_time_shift", "Shift by:"), row)
        self._reference = QDateTimeEdit()
        self._reference.setDisplayFormat(_QT_SHOWN)
        self._reference.setEnabled(bool(self._items))
        if self._items:
            self._reference.setDateTime(QDateTime(self._items[0][1]))
        self._reference.dateTimeChanged.connect(self._on_reference_edited)
        form.addRow(lang.get("capture_time_reference", "First photo really taken at:"),
                    self._reference)
        return form

    def delta(self) -> timedelta:
        """The shift the fields describe."""
        days, hours, minutes, seconds = (getattr(self, attr).value() for attr, *_ in _PARTS)
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

    def _on_shift_edited(self, _value: int) -> None:
        if self._items:
            self._reference.blockSignals(True)
            self._reference.setDateTime(QDateTime(self._shifted(self._items[0][1])))
            self._reference.blockSignals(False)
        self._show_preview()

    def _on_reference_edited(self, value: QDateTime) -> None:
        delta = delta_to_match(self._items[0][1], value.toPython())
        for (attr, *_), part in zip(_PARTS, split_delta(delta), strict=True):
            spin = getattr(self, attr)
            spin.blockSignals(True)
            spin.setValue(part)
            spin.blockSignals(False)
        self._show_preview()

    def _shifted(self, when: datetime) -> datetime:
        try:
            return when + self.delta()
        except OverflowError:
            return when

    def _show_preview(self) -> None:
        if not self._items:
            return
        path, when = self._items[0]
        self._preview.setText(f"{Path(path).name}: {when.strftime(_SHOWN)} → "
                              f"{self._shifted(when).strftime(_SHOWN)}")

    def apply(self) -> tuple[int, int]:
        """Rewrite every photo's capture time and report it; ``(written, failed)``."""
        lang = language_wrapper.language_word_dict
        try:
            written, failed = apply_shift(self._items, self.delta())
        except OverflowError:
            self._status.setText(lang.get(
                "capture_time_overflow", "That shift moves a photo outside the calendar."))
            return 0, 0
        self._status.setText(lang.get(
            "capture_time_done",
            "Rewrote {written} photo(s); {failed} could not be rewritten (only JPEG and WebP "
            "can be, and the file must be writable).",
        ).format(written=written, failed=failed))
        self._items = read_capture_times([path for path, _ in self._items])
        self._reset_shift()
        return written, failed

    def _reset_shift(self) -> None:
        """Back to a zero shift from the new times, so Apply can't shift twice by accident."""
        for attr, *_ in _PARTS:
            spin = getattr(self, attr)
            spin.blockSignals(True)
            spin.setValue(0)
            spin.blockSignals(False)
        self._on_shift_edited(0)


def open_capture_time(ui: ImervueMainWindow) -> None:
    """Open the dialog on the selection, or on every image the viewer lists."""
    CaptureTimeDialog(selection_or_all(getattr(ui, "viewer", None)), ui).exec()
