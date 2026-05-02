"""Histogram dock — render the active document's RGB / luma histogram.

Plots the four channels stacked vertically as small line graphs.
The dock subscribes to nothing in particular; the workspace pushes
fresh histograms via :meth:`HistogramDock.set_histogram` whenever
the document changes (throttled by the same coalesce timer as the
navigator preview).
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QDockWidget, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.histogram import (
    HISTOGRAM_BINS,
    Histogram,
    empty_histogram,
    normalise,
)

CHANNEL_COLORS: dict[str, QColor] = {
    "r": QColor("#ff5555"),
    "g": QColor("#55ff55"),
    "b": QColor("#5599ff"),
    "luma": QColor("#cccccc"),
}


class _HistogramView(QWidget):
    """Bare-metal QPainter renderer of a Histogram for one channel.

    Splitting the view out of the dock body keeps the paint code
    testable in isolation (see :func:`paintEvent`)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._histogram: Histogram = empty_histogram()
        self._channel = "luma"
        self.setMinimumHeight(120)
        self.setStyleSheet("background-color: #111;")

    def set_histogram(self, hist: Histogram) -> None:
        self._histogram = hist
        self.update()

    def set_channel(self, channel: str) -> None:
        if channel not in CHANNEL_COLORS:
            return
        self._channel = channel
        self.update()

    def channel(self) -> str:
        return self._channel

    def paintEvent(self, event):  # noqa: N802, ARG002
        del event
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#111"))
            channel = self._histogram.channel(self._channel)
            normalized = normalise(channel)
            w = max(1, self.width())
            h = max(1, self.height())
            pen = QPen(CHANNEL_COLORS[self._channel])
            pen.setWidth(1)
            painter.setPen(pen)
            # Map each of the 256 bins to a proportional x-coordinate.
            prev_x = 0
            prev_y = h
            for i, value in enumerate(normalized):
                x = int(round(i / (HISTOGRAM_BINS - 1) * (w - 1)))
                y = int(round(h - float(value) * h))
                if i > 0:
                    painter.drawLine(prev_x, prev_y, x, y)
                prev_x = x
                prev_y = y
        finally:
            painter.end()


class HistogramDock(QDockWidget):
    """Dock holding a channel selector + the histogram view."""

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(
            lang.get("paint_dock_histogram", "Histogram"), parent,
        )
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)

        controls = QHBoxLayout()
        controls.addWidget(QLabel(
            lang.get("paint_histogram_channel", "Channel"),
        ))
        self._channel_combo = QComboBox()
        for name, label_key, fallback in (
            ("luma", "paint_histogram_luma", "Luminance"),
            ("r", "paint_histogram_red", "Red"),
            ("g", "paint_histogram_green", "Green"),
            ("b", "paint_histogram_blue", "Blue"),
        ):
            self._channel_combo.addItem(
                lang.get(label_key, fallback), userData=name,
            )
        self._channel_combo.currentIndexChanged.connect(
            self._on_channel_changed,
        )
        controls.addWidget(self._channel_combo)
        controls.addStretch(1)
        layout.addLayout(controls)

        self._view = _HistogramView()
        layout.addWidget(self._view, stretch=1)

        self.setWidget(body)

    # ---- public API -----------------------------------------------------

    def set_histogram(self, hist: Histogram) -> None:
        self._view.set_histogram(hist)

    def view(self) -> _HistogramView:
        return self._view

    def channel(self) -> str:
        return self._view.channel()

    # ---- slots ----------------------------------------------------------

    def _on_channel_changed(self, _index: int) -> None:
        name = self._channel_combo.currentData()
        if isinstance(name, str):
            self._view.set_channel(name)
