"""
圖片名稱即時搜尋對話框
Real-time image filename search dialog.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QTextDocument, QPainter, QAbstractTextDocumentLayout
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QStyledItemDelegate, QStyle,
    QStyleOptionViewItem,
)

from Imervue.multi_language.language_wrapper import language_wrapper


class _HighlightDelegate(QStyledItemDelegate):
    """Renders list items as rich text so we can <b>-highlight query hits."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setHtml(options.text)
        # Clear the text so the default style paints only background+selection.
        options.text = ""

        style = options.widget.style() if options.widget else None
        if style is None:
            from PySide6.QtWidgets import QApplication
            style = QApplication.style()

        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()
        text_rect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, options, options.widget
        )
        painter.save()
        painter.translate(text_rect.topLeft())
        painter.setClipRect(text_rect.translated(-text_rect.topLeft()))
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width())
        return QSize(int(doc.idealWidth()), int(doc.size().height()))


def _fuzzy_score(haystack: str, needle: str) -> tuple[int, int]:
    """Simple fuzzy match score.

    Returns ``(rank, first_idx)`` where lower rank = better match. ``rank``:
    0 — exact start, 1 — substring, 2 — all characters appear in order,
    3 — no match (caller should skip).
    """
    if not needle:
        return 1, 0
    if haystack.startswith(needle):
        return 0, 0
    idx = haystack.find(needle)
    if idx >= 0:
        return 1, idx

    # Subsequence match: every char of needle appears in order in haystack
    i = 0
    first_idx = -1
    for j, ch in enumerate(haystack):
        if i < len(needle) and ch == needle[i]:
            if first_idx < 0:
                first_idx = j
            i += 1
    if i == len(needle):
        return 2, max(first_idx, 0)
    return 3, 0


def _highlight_html(name: str, keyword: str) -> str:
    """Wrap substring hits in <b> for rich-text display."""
    if not keyword:
        return _escape(name)
    lower_name = name.lower()
    lower_key = keyword.lower()
    idx = lower_name.find(lower_key)
    if idx < 0:
        return _escape(name)
    pre = _escape(name[:idx])
    hit = _escape(name[idx:idx + len(keyword)])
    post = _escape(name[idx + len(keyword):])
    return f"{pre}<b style='color:#ffcc66'>{hit}</b>{post}"


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class ImageSearchDialog(QDialog):

    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui

        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("search_dialog_title", "Search Images"))
        self.setMinimumSize(500, 400)
        self.resize(540, 460)

        layout = QVBoxLayout(self)

        # ===== 搜尋列 =====
        search_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText(
            lang.get("search_dialog_placeholder", "Type to search...")
        )
        self._input.setClearButtonEnabled(True)
        search_row.addWidget(self._input)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #888; font-size: 12px; padding: 0 6px;")
        search_row.addWidget(self._count_label)
        layout.addLayout(search_row)

        # ===== 結果列表 =====
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setItemDelegate(_HighlightDelegate(self._list))
        layout.addWidget(self._list, stretch=1)

        # ===== 按鈕列 =====
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        open_btn = QPushButton(lang.get("search_open", "Open"))
        open_btn.setDefault(True)
        open_btn.clicked.connect(self._activate_selected)
        btn_row.addWidget(open_btn)

        close_btn = QPushButton(lang.get("tip_close", "Close"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # ===== 資料 =====
        self._all_paths: list[str] = list(main_gui.model.images)
        self._filtered: list[str] = []

        # ===== 信號 =====
        self._input.textChanged.connect(self._on_text_changed)
        self._list.itemDoubleClicked.connect(lambda _: self._activate_selected())
        self._input.returnPressed.connect(self._activate_selected)

        # 初始顯示所有圖片
        self._on_text_changed("")
        self._input.setFocus()

    # ===========================
    # 即時篩選（模糊 + 排序 + 高亮）
    # ===========================
    def _on_text_changed(self, text: str):
        self._list.clear()
        keyword = text.strip().lower()
        self._filtered.clear()

        scored: list[tuple[int, int, str, str]] = []  # (rank, idx, path, name)
        for path in self._all_paths:
            name = Path(path).name
            rank, first_idx = _fuzzy_score(name.lower(), keyword)
            if rank >= 3:
                continue
            scored.append((rank, first_idx, path, name))

        # Sort: better rank first, then earlier hit position, then filename
        scored.sort(key=lambda t: (t[0], t[1], t[3].lower()))

        for _rank, _idx, path, name in scored:
            self._filtered.append(path)
            parent = Path(path).parent.name
            name_html = _highlight_html(name, keyword)
            if parent:
                display_html = (
                    f"{name_html} <span style='color:#777'>"
                    f"({_escape(parent)})</span>"
                )
            else:
                display_html = name_html
            item = QListWidgetItem(display_html)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)

        total = len(self._all_paths)
        matched = len(self._filtered)
        self._count_label.setText(f"{matched}/{total}")

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ===========================
    # 開啟選中的圖片
    # ===========================
    def _activate_selected(self):
        item = self._list.currentItem()
        if item is None:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        gui = self._main_gui

        if path not in gui.model.images:
            return

        idx = gui.model.images.index(path)
        gui.current_index = idx

        if gui.tile_grid_mode:
            # 縮圖模式 → 滾動定位到該圖片並高亮
            self._scroll_to_tile(idx)
        else:
            gui.load_deep_zoom_image(path)

        self.accept()

    def _scroll_to_tile(self, index: int):
        """在 Tile Grid 模式下滾動到指定圖片位置"""
        gui = self._main_gui

        base_tile = gui.thumbnail_size or 256
        scaled_tile = base_tile * gui.tile_scale
        cell = scaled_tile + gui.tile_padding
        cols = max(1, int(gui.width() // cell))

        row = index // cols
        target_y = -(row * cell) + gui.height() / 3

        gui.grid_offset_y = target_y
        gui.selected_tiles = {gui.model.images[index]}
        gui.tile_selection_mode = True
        gui.update()

    # ===========================
    # 鍵盤導航
    # ===========================
    def keyPressEvent(self, event):
        key = event.key()
        # 上下鍵在搜尋框中也能操作列表
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            current = self._list.currentRow()
            if key == Qt.Key.Key_Down:
                new_row = min(current + 1, self._list.count() - 1)
            else:
                new_row = max(current - 1, 0)
            self._list.setCurrentRow(new_row)
            return
        super().keyPressEvent(event)


def open_search_dialog(main_gui: GPUImageView):
    dlg = ImageSearchDialog(main_gui)
    dlg.exec()
