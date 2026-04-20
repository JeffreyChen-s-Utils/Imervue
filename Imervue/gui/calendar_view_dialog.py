"""
Calendar view dialog — browse the library by capture date.

Shows a calendar widget whose day-cells are badged with the image count
for that day; selecting a date lists the images taken on it and opens
the highlighted image in the main viewer on double-click.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
)

from Imervue.library.calendar_index import UNKNOWN_DATE, group_by_date
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.calendar_view_dialog")


def _library_paths(ui: "ImervueMainWindow") -> list[str]:
    viewer = getattr(ui, "viewer", None)
    model = getattr(viewer, "model", None)
    images = getattr(model, "images", None)
    return list(images) if images else []


class CalendarViewDialog(QDialog):
    def __init__(self, ui: "ImervueMainWindow"):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("calendar_title", "Calendar View"))
        self.resize(760, 520)

        self._by_date = group_by_date(_library_paths(ui))

        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.clicked.connect(self._on_date_clicked)

        self._highlight_days_with_images()

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._summary = QLabel(lang.get(
            "calendar_summary",
            "{days} day(s) with photos; {total} image(s) total.",
        ).format(
            days=sum(1 for d in self._by_date if d != UNKNOWN_DATE),
            total=sum(len(v) for v in self._by_date.values()),
        ))

        body = QHBoxLayout()
        body.addWidget(self._calendar, 1)
        body.addWidget(self._list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self._summary)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)

    def _highlight_days_with_images(self) -> None:
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(QColor(70, 130, 210, 80)))
        fmt.setFontWeight(75)  # bold
        for date, items in self._by_date.items():
            if date == UNKNOWN_DATE or not items:
                continue
            q = QDate(date.year, date.month, date.day)
            self._calendar.setDateTextFormat(q, fmt)

    def _on_date_clicked(self, qdate: QDate) -> None:
        date = _dt.date(qdate.year(), qdate.month(), qdate.day())
        items = self._by_date.get(date, [])
        self._list.clear()
        for p in items:
            self._list.addItem(p)

    def _on_item_double_clicked(self, item) -> None:
        path = item.text()
        viewer = getattr(self._ui, "viewer", None)
        loader = getattr(viewer, "load_image", None)
        if callable(loader):
            loader(path)


def open_calendar_view(ui: "ImervueMainWindow") -> None:
    CalendarViewDialog(ui).exec()
