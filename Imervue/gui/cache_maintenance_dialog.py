"""Thumbnail cache maintenance dialog."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from Imervue.image.thumbnail_disk_cache import thumbnail_disk_cache
from Imervue.multi_language.language_wrapper import language_wrapper


class CacheMaintenanceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lang = language_wrapper.language_word_dict
        self.setWindowTitle(self._lang.get("cache_maintenance_title", "Thumbnail Cache"))
        self.resize(420, 140)
        layout = QVBoxLayout(self)
        self._size = QLabel()
        layout.addWidget(self._size)
        row = QHBoxLayout()
        clear_btn = QPushButton(self._lang.get("cache_clear", "Clear cache"))
        clear_btn.clicked.connect(self._clear)
        close_btn = QPushButton(self._lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        row.addWidget(clear_btn)
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)
        self._refresh()

    def _refresh(self) -> None:
        size = thumbnail_disk_cache.total_bytes()
        self._size.setText(
            self._lang.get("cache_size", "Cache size: {size}").format(
                size=_format_bytes(size),
            )
        )

    def _clear(self) -> None:
        thumbnail_disk_cache.clear()
        self._refresh()


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024


def open_cache_maintenance(parent=None) -> None:
    CacheMaintenanceDialog(parent).exec()

