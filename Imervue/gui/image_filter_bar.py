"""Labelled, compact browse filters with date feedback and a single reset action."""
from __future__ import annotations

from collections import ChainMap
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.multi_language.english import english_word_dict
from Imervue.system.ui_scale import scaled_px


def filter_date(value: str) -> date | None:
    """Parse the optional ISO date used by browse filters."""
    try:
        return date.fromisoformat(value.strip()) if value.strip() else None
    except ValueError:
        return None


class ImageFilterBar(QWidget):
    """Two rows keep inputs usable when the folder and info docks are open."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("imageFilterBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QGridLayout(self)
        gap = scaled_px(6)
        self._layout.setContentsMargins(gap, scaled_px(4), gap, scaled_px(4))
        self._layout.setSpacing(gap)
        self._lang = ChainMap(language_wrapper.language_word_dict, english_word_dict)
        lang = self._lang
        self.filename = self._text_field("image_filter_filename_placeholder", 0, 0)
        self.tag = QComboBox()
        self.tag.setEditable(True)
        self.tag.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.tag.addItem(lang["image_filter_any_tag"], "")
        self.tag.currentTextChanged.connect(self.changed)
        self._field(self.tag, "image_filter_tag", 0, 1)
        self.rating = QComboBox()
        self.rating.addItem(lang["image_filter_any_rating"], "")
        for rating in range(1, 6):
            self.rating.addItem(f"≥ {rating} ★", f">={rating}")
        self.rating.currentIndexChanged.connect(self.changed)
        self._field(self.rating, "list_col_rating", 0, 2)
        self.date_from = self._text_field("image_filter_date_from", 2, 0, is_date=True)
        self.date_to = self._text_field("image_filter_date_to", 2, 1, is_date=True)
        self.reset = QPushButton(lang["image_filter_reset"])
        self.reset.setEnabled(False)
        self._layout.addWidget(self.reset, 3, 2)
        self.missing = QPushButton(lang.get("missing_batch_menu", "Missing"))
        self._layout.addWidget(self.missing, 1, 3)
        self.feedback = QLabel()
        self.feedback.setObjectName("filterFeedback")
        self.feedback.setWordWrap(True)
        self.feedback.setVisible(False)
        self._layout.addWidget(self.feedback, 4, 0, 1, 4)
        for column in range(3):
            self._layout.setColumnStretch(column, 1)

    def _field(self, widget: QWidget, key: str, row: int, column: int) -> None:
        title = self._lang[key]
        label = QLabel(title)
        label.setBuddy(widget)
        widget.setAccessibleName(title)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Avoid the combo's longest tag inflating the minimum window width.
        if isinstance(widget, QComboBox):
            widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(6)
        widget.setMinimumWidth(scaled_px(80))
        self._layout.addWidget(label, row, column)
        self._layout.addWidget(widget, row + 1, column)

    def _text_field(self, key: str, row: int, column: int, *, is_date=False) -> QLineEdit:
        field = QLineEdit()
        field.setClearButtonEnabled(True)
        placeholder = "YYYY-MM-DD" if is_date else self._lang[key]
        field.setPlaceholderText(placeholder)
        self._field(field, key, row, column)
        field.textChanged.connect(self.changed)
        return field

    def update_feedback(self, *, active: bool) -> None:
        """Explain ignored input without modal dialogs or stealing keyboard focus."""
        lang = self._lang
        start, end = filter_date(self.date_from.text()), filter_date(self.date_to.text())
        invalid = any(field.text().strip() and filter_date(field.text()) is None
                      for field in (self.date_from, self.date_to))
        message = ""
        if invalid:
            message = lang["image_filter_invalid_date"]
        elif start and end and start > end:
            message = lang["image_filter_invalid_range"]
        self.feedback.setText(message)
        self.feedback.setVisible(bool(message))
        self.reset.setEnabled(active)
