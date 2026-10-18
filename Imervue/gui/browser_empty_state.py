"""Actionable browse welcome, empty-folder and no-match states over the viewer."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.ui_scale import scaled_px


class BrowserEmptyState(QFrame):
    def __init__(self, viewer, *, open_folder, clear_filters, filter_active, folder_open):
        super().__init__(viewer)
        self.setObjectName("browserWelcome")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._viewer = viewer
        self._filter_active = filter_active
        self._folder_open = folder_open
        self._state = ""
        self._title = QLabel()
        font = QFont(self.font())
        font.setPointSizeF(max(1.0, font.pointSizeF()) + 4)
        font.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(font)
        self._subtitle = QLabel()
        self._subtitle.setObjectName("emptyStateSubtitle")
        for label in (self._title, self._subtitle):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
        self._open = QPushButton(self._word("main_window_open_folder"))
        self._open.setProperty("primary", True)
        self._open.clicked.connect(open_folder)
        self._clear = QPushButton(self._word("image_filter_reset"))
        self._clear.clicked.connect(clear_filters)
        layout = QVBoxLayout(self)
        side = scaled_px(28)
        layout.setContentsMargins(side, side, side, side)
        layout.setSpacing(scaled_px(16))
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self._open)
        actions.addWidget(self._clear)
        actions.addStretch()
        layout.addLayout(actions)
        self._viewer.installEventFilter(self)
        self.refresh()

    @staticmethod
    def _word(key):
        return language_wrapper.language_word_dict.get(key, english_word_dict[key])

    def refresh(self) -> None:
        if self._viewer.model.images or getattr(self._viewer, "_folder_scan_active", False):
            self.hide()
            return
        filtered = self._filter_active()
        state = "filtered"
        if not filtered:
            state = "folder" if self._folder_open() else "start"
        changed = state != self._state
        if changed:
            self._title.setText(self._word(f"browse_empty_{state}_title"))
            self._subtitle.setText(self._word(f"browse_empty_{state}_hint"))
            self._clear.setVisible(filtered)
            for button, primary in ((self._open, not filtered), (self._clear, filtered)):
                button.setProperty("primary", primary)
                button.style().unpolish(button)
                button.style().polish(button)
            self._state = state
        width = max(1, min(scaled_px(420), self._viewer.width() - scaled_px(24)))
        if changed or self.width() != width or self.isHidden():
            self.setFixedWidth(width)
            self.adjustSize()
        position = (max(0, (self._viewer.width() - self.width()) // 2),
                    max(0, (self._viewer.height() - self.height()) // 2))
        if (self.x(), self.y()) != position:
            self.move(*position)
        if self.isHidden():
            self.show()
            self.raise_()

    def eventFilter(self, watched, event):
        if watched is self._viewer and event.type() in (QEvent.Type.Paint, QEvent.Type.Resize,
                                                        QEvent.Type.Show):
            self.refresh()
        return False
