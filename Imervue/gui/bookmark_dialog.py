"""Bookmark manager dialog — browse and manage cross-folder image collections."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QLineEdit, QFileDialog,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.bookmark import (
    get_bookmarks, remove_bookmark, clear_bookmarks, add_bookmark,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.bookmark_dialog")

_EXPORT_TITLE = "Export Bookmarks"
_IMPORT_TITLE = "Import Bookmarks"


def open_bookmark_dialog(main_gui: GPUImageView):
    dlg = BookmarkDialog(main_gui)
    dlg.exec()


# ---------------------------------------------------------------------------
# Background exists() worker
# ---------------------------------------------------------------------------
# Path.exists() 會打 disk stat，對 NAS / 外接碟來說可能每次 10-100ms。
# 5000 筆書籤在 UI 執行緒上逐筆檢查會直接凍結對話框。丟到 thread pool 去跑，
# 分批 emit 回 UI 執行緒更新顯示顏色即可。
# Generation counter 用來避免使用者快速 refresh 時，舊 worker 的結果把新狀態蓋掉。


class _ExistsWorkerSignals(QObject):
    chunk = Signal(list, int)  # (List[Tuple[int, bool]], generation)


class _ExistsWorker(QRunnable):
    CHUNK_SIZE = 64

    def __init__(self, paths: list[str], generation: int):
        super().__init__()
        self.paths = paths
        self.generation = generation
        self.signals = _ExistsWorkerSignals()
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        buffer: list[tuple[int, bool]] = []
        for idx, p in enumerate(self.paths):
            if self._abort:
                return
            try:
                exists = Path(p).exists()
            except OSError:
                exists = False
            buffer.append((idx, exists))
            if len(buffer) >= self.CHUNK_SIZE:
                if self._abort:
                    return
                self.signals.chunk.emit(buffer, self.generation)
                buffer = []
        if buffer and not self._abort:
            self.signals.chunk.emit(buffer, self.generation)


class BookmarkDialog(QDialog):
    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui)
        self.main_gui = main_gui
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("bookmark_title", "Bookmarks"))
        self.setMinimumSize(560, 440)

        layout = QVBoxLayout(self)

        # Count label
        self._count_label = QLabel()
        layout.addWidget(self._count_label)

        # Search bar — 5000 筆清單沒有搜尋就是不能用
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            lang.get("bookmark_search_placeholder", "Search bookmarks...")
        )
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        # List
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        # Buttons — first row: open/remove/clear
        btn_row = QHBoxLayout()

        self._open_btn = QPushButton(lang.get("bookmark_open", "Open"))
        self._open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(self._open_btn)

        self._remove_btn = QPushButton(lang.get("bookmark_remove", "Remove"))
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._remove_btn)

        self._clear_btn = QPushButton(lang.get("bookmark_clear", "Clear All"))
        self._clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(self._clear_btn)

        layout.addLayout(btn_row)

        # Buttons — second row: import/export/close
        io_row = QHBoxLayout()

        self._import_btn = QPushButton(lang.get("bookmark_import", "Import..."))
        self._import_btn.clicked.connect(self._import_json)
        io_row.addWidget(self._import_btn)

        self._export_btn = QPushButton(lang.get("bookmark_export", "Export..."))
        self._export_btn.clicked.connect(self._export_json)
        io_row.addWidget(self._export_btn)

        io_row.addStretch()

        close_btn = QPushButton(lang.get("bookmark_close", "Close"))
        close_btn.clicked.connect(self.close)
        io_row.addWidget(close_btn)

        layout.addLayout(io_row)

        # ===== 背景 exists() worker 狀態 =====
        self._exists_generation = 0
        self._exists_worker: _ExistsWorker | None = None

        self._refresh()

    # ------------------------------------------------------------------
    # Refresh / background exists check
    # ------------------------------------------------------------------
    def _refresh(self):
        # 取消舊 worker（若有），避免它用過期的 generation 打到新列表上
        if self._exists_worker is not None:
            self._exists_worker.abort()
            self._exists_worker = None

        self._exists_generation += 1
        generation = self._exists_generation

        self._list.clear()
        bookmarks = get_bookmarks()
        lang = language_wrapper.language_word_dict
        self._count_label.setText(
            lang.get("bookmark_count", "{count} bookmarked image(s)").format(count=len(bookmarks))
        )
        # 立即把所有項目加進 list，顏色先保持預設（不 stat disk）
        for path in bookmarks:
            self._list.addItem(QListWidgetItem(path))

        # Re-apply any active filter so refresh doesn't clear the user's search.
        self._apply_filter(self._search.text())

        if not bookmarks:
            return

        worker = _ExistsWorker(list(bookmarks), generation)
        worker.signals.chunk.connect(self._on_exists_chunk)
        self._exists_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_exists_chunk(self, results, generation: int):
        if generation != self._exists_generation:
            return  # 過期的 worker
        for idx, exists in results:
            item = self._list.item(idx)
            if item is None:
                continue
            if not exists:
                item.setForeground(Qt.GlobalColor.gray)

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------
    def _apply_filter(self, text: str):
        """Case-insensitive substring filter across the full path."""
        needle = text.strip().lower()
        visible = 0
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not needle or needle in item.text().lower():
                item.setHidden(False)
                visible += 1
            else:
                item.setHidden(True)
        if needle:
            lang = language_wrapper.language_word_dict
            total = self._list.count()
            self._count_label.setText(
                lang.get(
                    "bookmark_filter_count",
                    "{visible} of {total} bookmark(s) match",
                ).format(visible=visible, total=total)
            )
        else:
            # No filter → reset to total count
            lang = language_wrapper.language_word_dict
            self._count_label.setText(
                lang.get(
                    "bookmark_count", "{count} bookmarked image(s)"
                ).format(count=self._list.count())
            )

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def _export_json(self):
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("bookmark_export_title", _EXPORT_TITLE),
            "imervue_bookmarks.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"bookmarks": get_bookmarks()},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except OSError as e:
            logger.error(f"Bookmark export failed: {e}")
            QMessageBox.warning(
                self,
                lang.get("bookmark_export_title", _EXPORT_TITLE),
                str(e),
            )
            return
        QMessageBox.information(
            self,
            lang.get("bookmark_export_title", _EXPORT_TITLE),
            lang.get(
                "bookmark_export_done",
                "Exported {count} bookmark(s).",
            ).format(count=len(get_bookmarks())),
        )

    def _import_json(self):
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("bookmark_import_title", _IMPORT_TITLE),
            "",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Bookmark import failed: {e}")
            QMessageBox.warning(
                self,
                lang.get("bookmark_import_title", _IMPORT_TITLE),
                str(e),
            )
            return
        # Accept either {"bookmarks": [...]} or a bare list, so plain text dumps
        # from 其他工具 (或手動編輯的 json) 也能匯入。
        if isinstance(data, dict):
            items = data.get("bookmarks", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []
        added = 0
        for entry in items:
            if isinstance(entry, str) and add_bookmark(entry):
                added += 1
        self._refresh()
        QMessageBox.information(
            self,
            lang.get("bookmark_import_title", _IMPORT_TITLE),
            lang.get(
                "bookmark_import_done",
                "Imported {added} new bookmark(s).",
            ).format(added=added),
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_double_click(self, item: QListWidgetItem):
        path = item.text()
        if Path(path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            self.main_gui.clear_tile_grid()
            open_path(main_gui=self.main_gui, path=path)
            self.close()

    def _open_selected(self):
        items = self._list.selectedItems()
        if not items:
            return
        path = items[0].text()
        if Path(path).is_file():
            from Imervue.gpu_image_view.images.image_loader import open_path
            self.main_gui.clear_tile_grid()
            open_path(main_gui=self.main_gui, path=path)
            self.close()

    def _remove_selected(self):
        items = self._list.selectedItems()
        for item in items:
            remove_bookmark(item.text())
        self._refresh()

    def _clear_all(self):
        lang = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self,
            lang.get("bookmark_clear_confirm_title", "Clear Bookmarks"),
            lang.get("bookmark_clear_confirm", "Remove all bookmarks?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_bookmarks()
            self._refresh()

    def closeEvent(self, event):
        if self._exists_worker is not None:
            self._exists_worker.abort()
            self._exists_worker = None
        super().closeEvent(event)
