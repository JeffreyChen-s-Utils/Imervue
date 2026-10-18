"""Small, palette-aware building blocks for workspace onboarding and settings."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from Imervue.system.ui_scale import scaled_px


class WorkspaceWelcome(QFrame):
    """An actionable empty state; callbacks belong to the workspace controller."""

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("workspaceWelcome")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(scaled_px(24),) * 4)
        layout.setSpacing(scaled_px(12))
        heading = QLabel(title)
        heading.setObjectName("workspaceHeading")
        font = QFont(heading.font())
        font.setPointSizeF(max(1, font.pointSizeF()) + 5)
        font.setWeight(QFont.Weight.DemiBold)
        heading.setFont(font)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        description = QLabel(subtitle)
        description.setObjectName("workspaceDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.setMinimumWidth(scaled_px(280))

    def add_action(self, text, callback, *, primary=False) -> QPushButton:
        button = QPushButton(text, self)
        button.setProperty("primary", primary)
        button.setMinimumHeight(scaled_px(36))
        button.clicked.connect(callback)
        self.layout().addWidget(button)
        return button
