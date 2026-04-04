"""
比較模式對話框
Side-by-side comparison dialog — display 2 or 4 images simultaneously.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QWidget, QScrollArea,
    QSizePolicy,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class _ImageLabel(QLabel):
    """自適應縮放的圖片標籤"""

    def __init__(self, path: str | None = None):
        super().__init__()
        self._pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        if path:
            self.load(path)

    def load(self, path: str):
        self._pixmap = QPixmap(path)
        self._update_scaled()

    def _update_scaled(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled()


class CompareDialog(QDialog):

    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui

        from Imervue.multi_language.language_wrapper import language_wrapper
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("compare_title", "Compare Images"))
        self.resize(1200, 800)

        main_layout = QHBoxLayout(self)

        # ===== 左側：圖片列表 =====
        left_panel = QVBoxLayout()

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for path in main_gui.model.images:
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)
        left_panel.addWidget(self._list)

        btn_layout = QHBoxLayout()

        btn_2 = QPushButton(lang.get("compare_2", "Compare 2"))
        btn_2.clicked.connect(lambda: self._compare(2))
        btn_layout.addWidget(btn_2)

        btn_4 = QPushButton(lang.get("compare_4", "Compare 4"))
        btn_4.clicked.connect(lambda: self._compare(4))
        btn_layout.addWidget(btn_4)

        left_panel.addLayout(btn_layout)
        main_layout.addLayout(left_panel, stretch=1)

        # ===== 右側：比較區域 =====
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(4)
        main_layout.addWidget(self._grid_widget, stretch=3)

        self._labels: list[_ImageLabel] = []

    def _compare(self, count: int):
        selected = self._list.selectedItems()
        paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected]

        if len(paths) < count:
            return

        paths = paths[:count]

        # 清除舊的
        for label in self._labels:
            self._grid_layout.removeWidget(label)
            label.deleteLater()
        self._labels.clear()

        if count == 2:
            rows, cols = 1, 2
        else:
            rows, cols = 2, 2

        for i, path in enumerate(paths):
            r, c = divmod(i, cols)
            label = _ImageLabel(path)
            self._grid_layout.addWidget(label, r, c)
            self._labels.append(label)


def open_compare_dialog(main_gui: GPUImageView):
    dlg = CompareDialog(main_gui)
    dlg.exec()
