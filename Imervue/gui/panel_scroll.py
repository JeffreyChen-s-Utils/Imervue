"""Scrollable dock content that cannot force the host beyond the available screen height."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QScrollArea

from Imervue.system.ui_scale import scaled_px


class PanelScrollArea(QScrollArea):
    def __init__(self, content, parent=None):
        super().__init__(parent)
        self.setObjectName("dockPanelScroll")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setWidget(content)

    def minimumSizeHint(self) -> QSize:
        return QSize(scaled_px(180), scaled_px(40))

    def sizeHint(self) -> QSize:
        return QSize(scaled_px(320), scaled_px(220))


def scroll_dock_content(dock) -> None:
    content = dock.widget()
    if content is not None and not isinstance(content, QScrollArea):
        dock.setWidget(PanelScrollArea(content, dock))
